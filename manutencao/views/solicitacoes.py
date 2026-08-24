from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from bedesk.models import Sala
from manutencao.forms import AtualizarStatusForm, SolicitacaoManutencaoForm
from manutencao.models import HistoricoManutencao, SolicitacaoManutencao
from notificacoes.services.notificar import (
    notificar_manutencao_atualizada,
    notificar_manutencao_criada,
)
from usuarios.permissions import is_admin_or_staff


# ----------------------------------------------------------------------
# Usuário
# ----------------------------------------------------------------------

@login_required
def criar_solicitacao(request):
    if request.method == 'POST':
        form = SolicitacaoManutencaoForm(request.POST, request.FILES)
        if form.is_valid():
            solicitacao = form.save(commit=False)
            solicitacao.solicitante = request.user
            solicitacao.status = SolicitacaoManutencao.ABERTA
            solicitacao.save()

            # O registro inicial entra no histórico para a linha do tempo
            # começar na abertura, e não na primeira mudança de status.
            HistoricoManutencao.objects.create(
                solicitacao=solicitacao,
                autor=request.user,
                status_anterior='',
                status_novo=solicitacao.status,
                observacao='Solicitação registrada.',
            )

            notificar_manutencao_criada(solicitacao)
            messages.success(request, 'Solicitação registrada. Você será avisado sobre o andamento.')
            return redirect('minhas_manutencoes')
    else:
        form = SolicitacaoManutencaoForm()

    return render(request, 'manutencao/criar.html', {'form': form})


@login_required
def minhas_solicitacoes(request):
    solicitacoes = SolicitacaoManutencao.objects.filter(
        solicitante=request.user
    ).select_related('sala')

    abertas = [s for s in solicitacoes if s.aberta]
    resolvidas = [s for s in solicitacoes if not s.aberta]

    return render(request, 'manutencao/minhas.html', {
        'abertas': abertas,
        'resolvidas': resolvidas,
        'total_abertas': len(abertas),
        'total_resolvidas': len(resolvidas),
    })


@login_required
def detalhe_solicitacao(request, pk):
    solicitacao = get_object_or_404(
        SolicitacaoManutencao.objects.select_related('sala', 'solicitante'), pk=pk
    )

    # Solicitação é do usuário ou ele opera o sistema.
    if solicitacao.solicitante != request.user and not is_admin_or_staff(request.user):
        messages.error(request, 'Você não tem acesso a esta solicitação.')
        return redirect('minhas_manutencoes')

    return render(request, 'manutencao/detalhe.html', {
        'solicitacao': solicitacao,
        'historico': solicitacao.historico.select_related('autor'),
        'pode_gerenciar': is_admin_or_staff(request.user),
        'form_status': AtualizarStatusForm(initial={
            'status': solicitacao.status,
            'prioridade': solicitacao.prioridade,
        }),
    })


# ----------------------------------------------------------------------
# Administração
# ----------------------------------------------------------------------

@login_required
@user_passes_test(is_admin_or_staff)
def painel_manutencao(request):
    solicitacoes = SolicitacaoManutencao.objects.select_related('sala', 'solicitante')

    # Filtros da barra superior. Valor vazio significa "sem filtro".
    f_status = request.GET.get('status', '')
    f_prioridade = request.GET.get('prioridade', '')
    f_sala = request.GET.get('sala', '')
    busca = request.GET.get('q', '').strip()

    if f_status == 'ABERTAS':
        solicitacoes = solicitacoes.filter(status__in=SolicitacaoManutencao.STATUS_ABERTOS)
    elif f_status:
        solicitacoes = solicitacoes.filter(status=f_status)

    if f_prioridade:
        solicitacoes = solicitacoes.filter(prioridade=f_prioridade)

    if f_sala:
        solicitacoes = solicitacoes.filter(sala_id=f_sala)

    if busca:
        solicitacoes = solicitacoes.filter(
            Q(descricao__icontains=busca)
            | Q(outro_local__icontains=busca)
            | Q(sala__nome__icontains=busca)
            | Q(solicitante__first_name__icontains=busca)
            | Q(solicitante__username__icontains=busca)
        )

    contagem = SolicitacaoManutencao.objects.aggregate(
        abertas=Count('pk', filter=Q(status=SolicitacaoManutencao.ABERTA)),
        analise=Count('pk', filter=Q(status=SolicitacaoManutencao.EM_ANALISE)),
        manutencao=Count('pk', filter=Q(status=SolicitacaoManutencao.EM_MANUTENCAO)),
        resolvidas=Count('pk', filter=Q(status=SolicitacaoManutencao.RESOLVIDA)),
    )

    pagina = Paginator(solicitacoes, 15).get_page(request.GET.get('page'))

    return render(request, 'manutencao/painel.html', {
        'solicitacoes': pagina,
        'salas': Sala.objects.order_by('nome'),
        'status_choices': SolicitacaoManutencao.STATUS_CHOICES,
        'prioridade_choices': SolicitacaoManutencao.PRIORIDADE_CHOICES,
        'f_status': f_status,
        'f_prioridade': f_prioridade,
        'f_sala': f_sala,
        'busca': busca,
        'contagem': contagem,
    })


@login_required
@user_passes_test(is_admin_or_staff)
@require_POST
def atualizar_status(request, pk):
    solicitacao = get_object_or_404(SolicitacaoManutencao, pk=pk)
    form = AtualizarStatusForm(request.POST)

    if not form.is_valid():
        messages.error(request, 'Não foi possível atualizar: verifique os campos.')
        return redirect('detalhe_manutencao', pk=pk)

    status_anterior = solicitacao.status
    novo_status = form.cleaned_data['status']
    observacao = form.cleaned_data['observacao'].strip()

    solicitacao.status = novo_status
    solicitacao.prioridade = form.cleaned_data['prioridade']
    solicitacao.resolvido_em = (
        timezone.now() if novo_status == SolicitacaoManutencao.RESOLVIDA else None
    )
    solicitacao.save()

    HistoricoManutencao.objects.create(
        solicitacao=solicitacao,
        autor=request.user,
        status_anterior=status_anterior,
        status_novo=novo_status,
        observacao=observacao,
    )

    # Só avisa o solicitante quando o status muda de fato: ajuste apenas
    # de prioridade ou observação interna não é novidade para ele.
    if status_anterior != novo_status:
        notificar_manutencao_atualizada(solicitacao, observacao)

    messages.success(request, f'Solicitação #{solicitacao.pk} atualizada.')
    return redirect('detalhe_manutencao', pk=pk)
