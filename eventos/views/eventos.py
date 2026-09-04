from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import IntegrityError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from eventos.forms import EventoForm
from eventos.models import Evento, InscricaoEvento
from eventos.services import liberar_espaco, reservar_espaco
from notificacoes.services.notificar import (
    notificar_evento_atualizado,
    notificar_evento_cancelado,
    notificar_evento_criado,
)
from usuarios.permissions import is_admin_or_staff


# ----------------------------------------------------------------------
# Usuário
# ----------------------------------------------------------------------

def lista_eventos(request):
    hoje = date.today()
    eventos = (
        Evento.objects.select_related('sala', 'responsavel')
        .annotate(inscritos=Count('inscricoes'))
    )

    busca = request.GET.get('q', '').strip()
    if busca:
        eventos = eventos.filter(
            Q(nome__icontains=busca)
            | Q(descricao__icontains=busca)
            | Q(sala__nome__icontains=busca)
        )

    proximos = eventos.filter(status=Evento.PROGRAMADO, data_fim__gte=hoje)
    encerrados = eventos.filter(
        Q(status=Evento.CANCELADO) | Q(data_fim__lt=hoje)
    ).order_by('-data_inicio')[:12]

    inscritos_em = set()
    if request.user.is_authenticated:
        inscritos_em = set(
            InscricaoEvento.objects.filter(usuario=request.user).values_list('evento_id', flat=True)
        )

    return render(request, 'eventos/lista.html', {
        'proximos': proximos,
        'encerrados': encerrados,
        'inscritos_em': inscritos_em,
        'busca': busca,
        'pode_gerenciar': is_admin_or_staff(request.user) if request.user.is_authenticated else False,
    })


def detalhe_evento(request, pk):
    evento = get_object_or_404(
        Evento.objects.select_related('sala', 'responsavel'), pk=pk
    )
    return render(request, 'eventos/detalhe.html', {
        'evento': evento,
        'minha_inscricao': evento.inscricao_de(request.user),
        'pode_gerenciar': request.user.is_authenticated and is_admin_or_staff(request.user),
    })


@login_required
@require_POST
def inscrever(request, pk):
    evento = get_object_or_404(Evento, pk=pk)

    if not evento.aberto_para_inscricao:
        if evento.cancelado:
            motivo = 'Este evento foi cancelado.'
        else:
            motivo = 'Este evento já foi encerrado.'
        messages.error(request, motivo)
        return redirect('detalhe_evento', pk=pk)

    try:
        InscricaoEvento.objects.create(evento=evento, usuario=request.user)
        messages.success(request, f'Inscrição confirmada em "{evento.nome}".')
    except IntegrityError:
        # Constraint do banco: clique duplo não vira inscrição duplicada.
        messages.info(request, 'Você já está inscrito neste evento.')

    return redirect('detalhe_evento', pk=pk)


@login_required
@require_POST
def cancelar_inscricao(request, pk):
    evento = get_object_or_404(Evento, pk=pk)
    removidas, _ = InscricaoEvento.objects.filter(evento=evento, usuario=request.user).delete()
    if removidas:
        messages.success(request, 'Inscrição cancelada.')
    return redirect('detalhe_evento', pk=pk)


# ----------------------------------------------------------------------
# Administração
# ----------------------------------------------------------------------

@login_required
@user_passes_test(is_admin_or_staff)
def criar_evento(request):
    if request.method == 'POST':
        form = EventoForm(request.POST)
        if form.is_valid():
            evento = form.save(commit=False)
            evento.criado_por = request.user
            evento.save()
            reservar_espaco(evento)
            notificar_evento_criado(evento)
            messages.success(request, f'Evento "{evento.nome}" criado e espaço reservado.')
            return redirect('detalhe_evento', pk=evento.pk)
    else:
        form = EventoForm(initial={'responsavel': request.user})

    return render(request, 'eventos/form.html', {'form': form, 'titulo': 'Criar evento'})


@login_required
@user_passes_test(is_admin_or_staff)
def editar_evento(request, pk):
    evento = get_object_or_404(Evento, pk=pk)

    if request.method == 'POST':
        form = EventoForm(request.POST, instance=evento)
        if form.is_valid():
            evento = form.save()
            # Horário ou sala podem ter mudado: refaz a ocupação da grade.
            reservar_espaco(evento)
            notificar_evento_atualizado(evento)
            messages.success(request, 'Evento atualizado.')
            return redirect('detalhe_evento', pk=evento.pk)
    else:
        form = EventoForm(instance=evento)

    return render(request, 'eventos/form.html', {
        'form': form,
        'titulo': f'Editar {evento.nome}',
        'evento': evento,
    })


@login_required
@user_passes_test(is_admin_or_staff)
@require_POST
def cancelar_evento(request, pk):
    evento = get_object_or_404(Evento, pk=pk)

    if evento.cancelado:
        messages.info(request, 'Este evento já estava cancelado.')
        return redirect('detalhe_evento', pk=pk)

    # Notifica antes de liberar, para a mensagem ainda citar o horário.
    notificar_evento_cancelado(evento)

    evento.status = Evento.CANCELADO
    evento.save()
    liberar_espaco(evento)  # devolve os horários à grade

    messages.success(request, f'Evento "{evento.nome}" cancelado e horários liberados.')
    return redirect('detalhe_evento', pk=pk)


@login_required
@user_passes_test(is_admin_or_staff)
def participantes(request, pk):
    evento = get_object_or_404(Evento, pk=pk)
    return render(request, 'eventos/participantes.html', {
        'evento': evento,
        'inscricoes': evento.inscricoes.select_related('usuario', 'usuario__profile'),
    })


@login_required
@user_passes_test(is_admin_or_staff)
@require_POST
def remover_participante(request, pk, inscricao_id):
    evento = get_object_or_404(Evento, pk=pk)
    InscricaoEvento.objects.filter(pk=inscricao_id, evento=evento).delete()
    messages.success(request, 'Participante removido.')
    return redirect('participantes_evento', pk=pk)
