from bedesk.models import Agendamento
from manutencao.models import SolicitacaoManutencao
from notificacoes.models import Notificacao


def notificacoes_pendentes(request):
    total_pendentes = 0
    notificacoes_nao_lidas = 0

    if request.user.is_authenticated:
        notificacoes_nao_lidas = Notificacao.objects.filter(
            destinatario=request.user,
            lida=False,
        ).count()

        if request.user.is_staff:
            total_pendentes = (
                Agendamento.objects.filter(status="PENDENTE").count()
                + SolicitacaoManutencao.objects.filter(
                    status__in=SolicitacaoManutencao.STATUS_ABERTOS
                ).count()
            )

    return {
        "pendentes_count": total_pendentes,
        "notificacoes_nao_lidas": notificacoes_nao_lidas,
    }
