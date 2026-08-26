from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from bedesk.models import Agendamento, Sala
from notificacoes.services.notificar import (
    notificar_reserva_criada,
    notificar_reserva_cancelada,
)
from reservas.forms import AgendarForm


@login_required
def agendar_sala(request):
    # A página deixou de ser um ponto de entrada: quem chega sem escolher
    # horário na grade vai escolher o local primeiro. O formulário só abre
    # a partir de um slot (com sala/data/hora na query) ou no POST.
    if request.method == "GET" and not request.GET.get("sala"):
        return redirect("lista_locais")

    initial_data, context_predefinido = _get_dados_predefinidos(request)

    if request.method == "POST":
        form = AgendarForm(request.POST)
        if form.is_valid():
            nova_reserva = form.save(commit=False)
            if nova_reserva.data_inicio and nova_reserva.horario:
                nova_reserva.data_inicio = datetime.combine(
                    nova_reserva.data_inicio.date(),
                    nova_reserva.horario,
                )
            nova_reserva.usuario = request.user
            nova_reserva.status = "PENDENTE"
            nova_reserva.save()
            notificar_reserva_criada(nova_reserva)
            return redirect("reserva_sucesso")
    else:
        form = AgendarForm(initial=initial_data)

    context = {"form": form, **context_predefinido}
    return render(request, "reservas/agendar.html", context)


@login_required
def lista_reservas(request):
    today = date.today()

    reservas_ativas = Agendamento.objects.filter(
        usuario=request.user,
        data_inicio__date__gte=today,
        status__in=["APROVADO", "PENDENTE"],
    ).order_by("data_inicio", "horario")

    reservas_historico = (
        Agendamento.objects.filter(usuario=request.user)
        .exclude(pk__in=reservas_ativas.values_list("pk", flat=True))
        .order_by("-data_inicio", "horario")
    )

    historico_page = Paginator(reservas_historico, 10).get_page(request.GET.get("page"))

    context = {
        "reservas_ativas": reservas_ativas,
        "reservas_historico": historico_page,
        "kpi_proximas": reservas_ativas.count(),
        "kpi_aprovadas": reservas_ativas.filter(status="APROVADO").count(),
        "kpi_pendentes": reservas_ativas.filter(status="PENDENTE").count(),
    }
    return render(request, "reservas/lista_reservas.html", context)


@login_required
@require_POST
def cancelar_reserva_usuario(request, agendamento_id):
    reserva = get_object_or_404(Agendamento, pk=agendamento_id, usuario=request.user)

    if reserva.status in ["PENDENTE", "APROVADO"]:
        reserva.status = "REJEITADO"
        reserva.save()
        notificar_reserva_cancelada(reserva)
        messages.success(request, "Reserva foi cancelada com sucesso.")
    else:
        messages.warning(request, "Esta reserva não pode ser cancelada.")

    return redirect("lista_reserva")


def _get_dados_predefinidos(request):
    hora_predefinida_str = request.GET.get("hora")
    data_predefinida_str = request.GET.get("data")
    sala_nome = request.GET.get("sala")

    sala_obj = None
    if sala_nome:
        sala_obj = Sala.objects.filter(nome__iexact=sala_nome).first()

    data_predefinida = _parse_date(data_predefinida_str)
    hora_predefinida_obj = _parse_time(hora_predefinida_str)
    datetime_predefinido = None

    if data_predefinida and hora_predefinida_obj:
        datetime_predefinido = datetime.combine(data_predefinida, hora_predefinida_obj)

    return (
        {
            "horario": hora_predefinida_obj,
            "data_inicio": datetime_predefinido,
            "sala": sala_obj,
        },
        {
            "hora_predefinida": hora_predefinida_str,
            "data_predefinida": data_predefinida,
            "sala_predefinida": sala_nome,
        },
    )


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_time(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError:
        return None
