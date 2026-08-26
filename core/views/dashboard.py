import datetime
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count
from django.db.models.functions import ExtractHour, ExtractWeekDay, TruncMonth
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from bedesk.models import Agendamento, Sala
from notificacoes.services.notificar import (
    notificar_reserva_aprovada,
    notificar_reserva_rejeitada,
)
from usuarios.permissions import is_admin_or_staff

STATUS_GERENCIAVEIS = ["APROVADO", "REJEITADO"]

MESES_NOMES = [
    'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
    'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez',
]

# Período selecionável no dashboard -> quantos dias para trás.
# None = todo o histórico.
PERIODOS = {
    'mes': ('Este mês', 30),
    '3meses': ('Últimos 3 meses', 90),
    'ano': ('Últimos 12 meses', 365),
    'tudo': ('Todo o período', None),
}
PERIODO_PADRAO = 'tudo'


@login_required
@user_passes_test(is_admin_or_staff)
def gerenciar_reservas(request):
    """Dashboard estatístico. A operação (aprovar/rejeitar) fica em
    `aprovacoes`, para esta página tratar só de números."""
    periodo = request.GET.get('periodo')
    if periodo not in PERIODOS:
        periodo = PERIODO_PADRAO
    _, dias = PERIODOS[periodo]

    hoje = datetime.date.today()
    reservas = Agendamento.objects.all()
    if dias:
        reservas = reservas.filter(data_inicio__date__gte=hoje - datetime.timedelta(days=dias))

    # --- KPIs ---
    total_reservas = reservas.count()
    aprovadas = reservas.filter(status="APROVADO").count()
    rejeitadas = reservas.filter(status="REJEITADO").count()
    pendentes = reservas.filter(status="PENDENTE").count()

    # Antes chamado de "taxa de ocupação", mas o cálculo sempre foi
    # aprovadas/total — ou seja, taxa de aprovação. Nome corrigido, e
    # agora considera só o que já foi decidido.
    decididas = aprovadas + rejeitadas
    taxa_aprovacao = int((aprovadas / decididas) * 100) if decididas else 0

    # Pendências são ação, não recorte: sempre o total do sistema.
    total_pendencias = Agendamento.objects.filter(status="PENDENTE").count()

    # --- Gráficos ---
    top_locais = (
        reservas.filter(sala__isnull=False)
        .values('sala__nome')
        .annotate(total=Count('id'))
        .order_by('-total')[:5]
    )
    locais_labels = [l['sala__nome'] for l in top_locais]
    locais_data = [l['total'] for l in top_locais]
    local_top = locais_labels[0] if locais_labels else '—'

    status_labels = ['Aprovadas', 'Pendentes', 'Rejeitadas']
    status_data = [aprovadas, pendentes, rejeitadas]

    # Reservas por mês (últimos 6 meses, independente do filtro, para
    # a linha temporal sempre mostrar tendência).
    meses_labels = []
    meses_dict = {}
    curr = (hoje.replace(day=1) - datetime.timedelta(days=150)).replace(day=1)
    for _ in range(6):
        meses_dict[f"{curr.year}-{curr.month:02d}"] = 0
        meses_labels.append(MESES_NOMES[curr.month - 1])
        curr = (curr.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)

    inicio_serie = hoje - datetime.timedelta(days=200)
    for item in (
        Agendamento.objects.filter(data_inicio__date__gte=inicio_serie)
        .annotate(mes=TruncMonth('data_inicio'))
        .values('mes')
        .annotate(total=Count('id'))
    ):
        if item['mes']:
            chave = f"{item['mes'].year}-{item['mes'].month:02d}"
            if chave in meses_dict:
                meses_dict[chave] += item['total']

    meses_data = list(meses_dict.values())

    # Ocupação por dia da semana (ExtractWeekDay: 1=domingo … 7=sábado)
    dias_semana = {n: 0 for n in range(1, 8)}
    for item in (
        reservas.filter(data_inicio__isnull=False)
        .annotate(dia=ExtractWeekDay('data_inicio'))
        .values('dia')
        .annotate(total=Count('id'))
    ):
        dias_semana[item['dia']] = item['total']

    dia_labels = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']
    dia_data = [dias_semana[n] for n in (2, 3, 4, 5, 6, 7, 1)]

    # Distribuição por horário (07h–18h, faixa de funcionamento)
    horas = {h: 0 for h in range(7, 19)}
    for item in (
        reservas.annotate(hora=ExtractHour('horario'))
        .values('hora')
        .annotate(total=Count('id'))
    ):
        if item['hora'] in horas:
            horas[item['hora']] = item['total']

    hora_labels = [f"{h:02d}h" for h in horas]
    hora_data = list(horas.values())
    pico = max(horas, key=horas.get) if any(horas.values()) else None
    horario_pico = f"{pico:02d}h" if pico is not None else '—'

    context = {
        "periodo": periodo,
        "periodos": [(chave, rotulo) for chave, (rotulo, _) in PERIODOS.items()],
        "periodo_label": PERIODOS[periodo][0],

        "kpi_total_reservas": total_reservas,
        "kpi_locais_ativos": Sala.objects.count(),
        "kpi_taxa_aprovacao": taxa_aprovacao,
        "kpi_pendencias": total_pendencias,
        "kpi_local_top": local_top,
        "kpi_horario_pico": horario_pico,

        "locais_labels": json.dumps(locais_labels),
        "locais_data": json.dumps(locais_data),
        "status_labels": json.dumps(status_labels),
        "status_data": json.dumps(status_data),
        "meses_labels": json.dumps(meses_labels),
        "meses_data": json.dumps(meses_data),
        "dia_labels": json.dumps(dia_labels),
        "dia_data": json.dumps(dia_data),
        "hora_labels": json.dumps(hora_labels),
        "hora_data": json.dumps(hora_data),
        "tem_dados": total_reservas > 0,
    }
    return render(request, "core/gerenciar.html", context)


@login_required
@user_passes_test(is_admin_or_staff)
def aprovacoes(request):
    """Fila operacional: aprovar ou rejeitar solicitações."""
    pendentes = (
        Agendamento.objects.filter(status="PENDENTE", sala__isnull=False)
        .select_related('sala', 'usuario')
        .order_by('data_inicio', 'horario')
    )
    decididas = (
        Agendamento.objects.filter(status__in=STATUS_GERENCIAVEIS, sala__isnull=False)
        .select_related('sala', 'usuario')
        .order_by('-data_inicio')[:15]
    )
    return render(request, "core/aprovacoes.html", {
        "pendentes": pendentes,
        "decididas": decididas,
        "total_pendentes": pendentes.count(),
        # Para o template distinguir solicitação futura de vencida: sem
        # isso, uma data já passada exibia "em 0 minuto".
        "agora": timezone.now(),
    })


@user_passes_test(is_admin_or_staff)
@require_POST
def mudar_status_reserva(request, agendamento_id, novo_status):
    if novo_status not in STATUS_GERENCIAVEIS:
        return JsonResponse({"success": False, "erro": "Status inválido"}, status=400)

    reserva = get_object_or_404(Agendamento, pk=agendamento_id)

    # Como pendente não bloqueia mais o horário, dois pedidos podem existir
    # para o mesmo slot. A trava passa para cá: só a primeira aprovação
    # ocupa a grade, a segunda é barrada.
    if novo_status == "APROVADO":
        ocupado = (
            Agendamento.objects.filter(
                sala=reserva.sala,
                data_inicio__date=reserva.data_inicio.date(),
                horario=reserva.horario,
                status="APROVADO",
            )
            .exclude(pk=reserva.pk)
            .exists()
        )
        if ocupado:
            aviso = (
                f'Já existe reserva aprovada para {reserva.sala.nome} '
                f'às {reserva.horario.strftime("%H:%M")} de '
                f'{reserva.data_inicio.strftime("%d/%m/%Y")}.'
            )
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"success": False, "erro": aviso}, status=409)
            messages.error(request, aviso)
            return redirect("aprovacoes")

    reserva.status = novo_status
    reserva.save()

    if novo_status == 'APROVADO':
        notificar_reserva_aprovada(reserva)
    elif novo_status == 'REJEITADO':
        notificar_reserva_rejeitada(reserva)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(
            {
                "success": True,
                "id": reserva.id,
                "novo_status": reserva.status,
                "usuario": reserva.usuario.username,
            }
        )
    return redirect("aprovacoes")
