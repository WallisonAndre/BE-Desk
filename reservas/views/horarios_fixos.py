"""Cadastro dos horários fixos dos espaços, no painel administrativo."""

from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from bedesk.models import Agendamento
from eventos.models import Evento
from reservas.forms import HorarioFixoForm
from reservas.models import HorarioFixo
from reservas.views.salas import faixas_do_horario_fixo
from usuarios.permissions import is_admin_or_staff

# Quanto olhar para a frente ao avisar sobre choques já marcados.
SEMANAS_DE_AVISO = 8


def _reservas_ja_marcadas(horario_fixo):
    """Reservas aprovadas que caem no horário fixo daqui para a frente."""
    faixas = faixas_do_horario_fixo(horario_fixo)
    if not faixas:
        return []
    hoje = date.today()
    return list(
        Agendamento.objects.filter(
            sala=horario_fixo.sala,
            status="APROVADO",
            horario__in=faixas,
            data_inicio__date__gte=hoje,
            data_inicio__date__lte=hoje + timedelta(weeks=SEMANAS_DE_AVISO),
            data_inicio__iso_week_day=horario_fixo.dia_semana + 1,
        ).order_by("data_inicio")
    )


def _eventos_ja_marcados(horario_fixo):
    """Eventos programados cuja janela encosta no horário fixo, no mesmo dia da semana."""
    hoje = date.today()
    candidatos = Evento.objects.filter(
        sala=horario_fixo.sala,
        status=Evento.PROGRAMADO,
        data_fim__gte=hoje,
        horario_inicio__lt=horario_fixo.horario_fim,
        horario_fim__gt=horario_fixo.horario_inicio,
    )
    encontrados = []
    for evento in candidatos:
        dia = max(evento.data_inicio, hoje)
        while dia <= evento.data_fim:
            if dia.weekday() == horario_fixo.dia_semana:
                encontrados.append(evento)
                break
            dia += timedelta(days=1)
    return encontrados


def avisar_sobre_choques(request, horario_fixo):
    """Avisa, sem impedir: quem manda no horário é o horário fixo."""
    reservas = _reservas_ja_marcadas(horario_fixo)
    eventos = _eventos_ja_marcados(horario_fixo)
    if not reservas and not eventos:
        return

    partes = []
    if reservas:
        datas = ", ".join(f"{r.data_inicio:%d/%m}" for r in reservas[:4])
        extra = f" e mais {len(reservas) - 4}" if len(reservas) > 4 else ""
        partes.append(f"{len(reservas)} reserva(s) aprovada(s) em {datas}{extra}")
    if eventos:
        partes.append(
            "o(s) evento(s) " + ", ".join(f'"{e.nome}"' for e in eventos[:4])
        )
    messages.warning(
        request,
        "Atenção: já havia " + " e ".join(partes)
        + " neste horário. O horário fixo passa a valer, mas esses compromissos "
        "continuam marcados e precisam ser resolvidos à mão.",
    )


@login_required
@user_passes_test(is_admin_or_staff)
def lista_horarios_fixos(request):
    horarios = HorarioFixo.objects.select_related("sala")
    return render(request, "reservas/horarios_fixos_lista.html", {"horarios": horarios})


@login_required
@user_passes_test(is_admin_or_staff)
def criar_horario_fixo(request):
    if request.method == "POST":
        form = HorarioFixoForm(request.POST)
        if form.is_valid():
            horario_fixo = form.save(commit=False)
            horario_fixo.criado_por = request.user
            horario_fixo.save()
            avisar_sobre_choques(request, horario_fixo)
            messages.success(request, "Horário fixo cadastrado.")
            return redirect("lista_horarios_fixos")
    else:
        form = HorarioFixoForm()

    return render(request, "reservas/horarios_fixos_form.html", {
        "form": form,
        "titulo": "Novo horário fixo",
    })


@login_required
@user_passes_test(is_admin_or_staff)
def editar_horario_fixo(request, pk):
    horario_fixo = get_object_or_404(HorarioFixo, pk=pk)

    if request.method == "POST":
        form = HorarioFixoForm(request.POST, instance=horario_fixo)
        if form.is_valid():
            horario_fixo = form.save()
            avisar_sobre_choques(request, horario_fixo)
            messages.success(request, "Horário fixo atualizado.")
            return redirect("lista_horarios_fixos")
    else:
        form = HorarioFixoForm(instance=horario_fixo)

    return render(request, "reservas/horarios_fixos_form.html", {
        "form": form,
        "titulo": f"Editar {horario_fixo.descricao}",
        "horario_fixo": horario_fixo,
    })


@login_required
@user_passes_test(is_admin_or_staff)
@require_POST
def remover_horario_fixo(request, pk):
    horario_fixo = get_object_or_404(HorarioFixo, pk=pk)
    descricao, sala = horario_fixo.descricao, horario_fixo.sala.nome
    horario_fixo.delete()
    messages.success(
        request, f'Horário fixo "{descricao}" removido. O horário voltou a ficar livre em {sala}.'
    )
    return redirect("lista_horarios_fixos")
