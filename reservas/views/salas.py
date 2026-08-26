from datetime import date, datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from bedesk.models import Agendamento, Sala


HORARIOS_ESTRUTURA = [
    {"tipo": "separador", "nome": "Manhã"},
    {"tipo": "hora", "inicio": "07:00", "fim": "07:45"},
    {"tipo": "hora", "inicio": "07:45", "fim": "08:30"},
    {"tipo": "intervalo", "inicio": "08:30", "fim": "08:50", "nome": "Intervalo (20 min)"},
    {"tipo": "hora", "inicio": "08:50", "fim": "09:35"},
    {"tipo": "hora", "inicio": "09:35", "fim": "10:20"},
    {"tipo": "intervalo", "inicio": "10:20", "fim": "10:30", "nome": "Intervalo (10 min)"},
    {"tipo": "hora", "inicio": "10:30", "fim": "11:15"},
    {"tipo": "hora", "inicio": "11:15", "fim": "12:00"},
    {"tipo": "separador", "nome": "Tarde"},
    {"tipo": "hora", "inicio": "13:00", "fim": "13:45"},
    {"tipo": "hora", "inicio": "13:45", "fim": "14:30"},
    {"tipo": "intervalo", "inicio": "14:30", "fim": "14:50", "nome": "Intervalo (20 min)"},
    {"tipo": "hora", "inicio": "14:50", "fim": "15:35"},
    {"tipo": "hora", "inicio": "15:35", "fim": "16:20"},
    {"tipo": "intervalo", "inicio": "16:20", "fim": "16:30", "nome": "Intervalo (10 min)"},
    {"tipo": "hora", "inicio": "16:30", "fim": "17:15"},
    {"tipo": "hora", "inicio": "17:15", "fim": "18:00"},
]

DIAS_SEMANA_NOMES = [
    "Segunda-feira",
    "Terça-feira",
    "Quarta-feira",
    "Quinta-feira",
    "Sexta-feira",
]


@login_required
def lista_locais(request):
    locais = Sala.objects.all().order_by("nome")
    return render(request, "reservas/lista_locais.html", {"locais": locais})


def detalhe_sala(request, nome_sala):
    data_foco = _get_data_foco(request.GET.get("foco"))
    today = date.today()
    start_of_current_week = today - timedelta(days=today.weekday())
    start_of_week = data_foco - timedelta(days=data_foco.weekday())
    dias_semana_datas = [start_of_week + timedelta(days=i) for i in range(5)]

    sala_obj = get_object_or_404(Sala, nome__iexact=nome_sala)
    # Só reserva aprovada ocupa a grade. Pendente ainda é um pedido: não
    # deve bloquear visualmente o horário nem para quem pediu nem para os
    # demais, já que pode acabar rejeitada.
    agendamentos = Agendamento.objects.filter(
        sala=sala_obj,
        status="APROVADO",
        data_inicio__date__range=[start_of_week, dias_semana_datas[-1]],
    ).select_related("usuario")

    agendamentos_map = {
        (ag.horario.strftime("%H:%M"), ag.data_inicio.weekday()): ag
        for ag in agendamentos
    }

    context = {
        "tabela_horarios": _build_tabela_horarios(dias_semana_datas, agendamentos_map),
        "dias_semana_nomes": DIAS_SEMANA_NOMES,
        "sala": sala_obj,
        "faixa_datas_semana": {
            "inicio": start_of_week.strftime("%d/%m/%Y"),
            "fim": dias_semana_datas[-1].strftime("%d/%m/%Y"),
        },
        "dias_com_data": _build_dias_com_data(dias_semana_datas),
        "semana_anterior": (start_of_week - timedelta(days=7)).strftime("%Y-%m-%d"),
        "proxima_semana": (start_of_week + timedelta(days=7)).strftime("%Y-%m-%d"),
        "status_semana": "PASSADA" if start_of_week < start_of_current_week else "FUTURA",
    }
    return render(request, "reservas/detalhe_sala.html", context)


def _get_data_foco(data_foco_str):
    if not data_foco_str:
        return date.today()

    try:
        return datetime.strptime(data_foco_str, "%Y-%m-%d").date()
    except ValueError:
        return date.today()


def _build_tabela_horarios(dias_semana_datas, agendamentos_map):
    tabela_horarios = []
    agora = datetime.now()

    for item in HORARIOS_ESTRUTURA:
        if item["tipo"] != "hora":
            tabela_horarios.append(item)
            continue

        hora_inicio_str = item["inicio"]
        hora_inicio = datetime.strptime(hora_inicio_str, "%H:%M").time()

        tabela_horarios.append(
            {
                "tipo": "hora",
                "horario_str": f"{item['inicio']} às {item['fim']}",
                "hora_para_link": hora_inicio_str,
                "celulas": [
                    {
                        "data": data_do_dia,
                        "agendamento": agendamentos_map.get((hora_inicio_str, dia_num)),
                        # Horário que já começou não é mais reservável.
                        "passado": datetime.combine(data_do_dia, hora_inicio) < agora,
                    }
                    for dia_num, data_do_dia in enumerate(dias_semana_datas)
                ],
            }
        )

    return tabela_horarios


def _build_dias_com_data(dias_semana_datas):
    return [
        {"nome_dia": nome, "data_formatada": data_obj.strftime("%d/%m")}
        for nome, data_obj in zip(DIAS_SEMANA_NOMES, dias_semana_datas)
    ]
