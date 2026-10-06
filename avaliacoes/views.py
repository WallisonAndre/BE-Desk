"""Avaliação dos espaços: o registro pelo usuário e os indicadores do admin."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404, redirect, render

from avaliacoes.forms import AvaliacaoForm
from avaliacoes.models import Avaliacao
from avaliacoes.services import (
    MINIMO_PARA_RANKING,
    medias_por_espaco,
    melhor_e_pior,
    motivo_para_nao_avaliar,
    reservas_avaliaveis,
)
from bedesk.models import Agendamento, Sala
from usuarios.permissions import is_admin_or_staff

COMENTARIOS_POR_PAGINA = 10


@login_required
def avaliar_reserva(request, agendamento_id):
    """Formulário de avaliação de uma reserva já usada."""
    reserva = get_object_or_404(Agendamento.objects.select_related("sala"), pk=agendamento_id)

    motivo = motivo_para_nao_avaliar(reserva, request.user)
    if motivo:
        messages.error(request, motivo)
        return redirect("minhas_avaliacoes")

    if request.method == "POST":
        form = AvaliacaoForm(request.POST)
        if form.is_valid():
            avaliacao = form.save(commit=False)
            avaliacao.reserva = reserva
            try:
                avaliacao.save()
            except IntegrityError:
                # Dois envios do mesmo formulário: o segundo esbarra no
                # vínculo um-para-um e não vira uma segunda avaliação.
                messages.error(request, "Você já avaliou esta reserva.")
                return redirect("minhas_avaliacoes")
            messages.success(
                request,
                f'Avaliação registrada. Obrigado por avaliar o espaço "{reserva.sala.nome}".',
            )
            return redirect("minhas_avaliacoes")
    else:
        form = AvaliacaoForm()

    return render(request, "avaliacoes/avaliar.html", {"form": form, "reserva": reserva})


@login_required
def minhas_avaliacoes(request):
    """O que a pessoa já avaliou e o que ainda pode avaliar."""
    avaliacoes = (
        Avaliacao.objects.filter(reserva__usuario=request.user)
        .select_related("reserva", "reserva__sala")
    )
    pendentes = reservas_avaliaveis(request.user)
    resumo = avaliacoes.aggregate(media=Avg("nota"))

    context = {
        "avaliacoes": avaliacoes,
        "pendentes": pendentes,
        "kpi_total": avaliacoes.count(),
        "kpi_pendentes": len(pendentes),
        "kpi_media": round(resumo["media"], 1) if resumo["media"] is not None else None,
    }
    return render(request, "avaliacoes/minhas_avaliacoes.html", context)


@login_required
@user_passes_test(is_admin_or_staff)
def indicadores(request):
    """Médias por espaço, melhores e piores, e os comentários recebidos."""
    medias = medias_por_espaco()
    melhor, pior = melhor_e_pior(medias)

    comentarios = (
        Avaliacao.objects.exclude(comentario="")
        .select_related("reserva", "reserva__sala", "reserva__usuario")
    )
    sala_escolhida = request.GET.get("sala") or ""
    if sala_escolhida.isdigit():
        comentarios = comentarios.filter(reserva__sala_id=int(sala_escolhida))

    pagina = Paginator(comentarios, COMENTARIOS_POR_PAGINA).get_page(request.GET.get("page"))
    geral = Avaliacao.objects.aggregate(media=Avg("nota"), total=Count("id"))

    context = {
        "medias": medias,
        "melhor": melhor,
        "pior": pior,
        "minimo_para_ranking": MINIMO_PARA_RANKING,
        "comentarios": pagina,
        "salas": Sala.objects.order_by("nome"),
        "sala_escolhida": sala_escolhida,
        "kpi_total": geral["total"],
        "kpi_media": round(geral["media"], 1) if geral["media"] is not None else None,
        "kpi_espacos_avaliados": sum(1 for linha in medias if linha["total"]),
    }
    return render(request, "avaliacoes/indicadores.html", context)
