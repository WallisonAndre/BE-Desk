from notificacoes.models import Notificacao


def criar_notificacao(destinatario, titulo, mensagem, tipo='SISTEMA', link=''):
    return Notificacao.objects.create(
        destinatario=destinatario,
        titulo=titulo,
        mensagem=mensagem,
        tipo=tipo,
        link=link,
    )


def notificar_reserva_criada(agendamento):
    from django.contrib.auth.models import User
    admins = User.objects.filter(is_staff=True, is_active=True)
    for admin in admins:
        criar_notificacao(
            destinatario=admin,
            titulo='Nova solicitação de reserva',
            mensagem=f'{agendamento.usuario.get_full_name() or agendamento.usuario.username} solicitou a sala "{agendamento.sala.nome}" para {agendamento.data_inicio.strftime("%d/%m/%Y")} às {agendamento.horario.strftime("%H:%M")}.',
            tipo='ADMIN_NOVA_SOLICITACAO',
            link='/gerenciar/',
        )
    criar_notificacao(
        destinatario=agendamento.usuario,
        titulo='Reserva enviada',
        mensagem=f'Sua reserva para a sala "{agendamento.sala.nome}" em {agendamento.data_inicio.strftime("%d/%m/%Y")} às {agendamento.horario.strftime("%H:%M")} foi enviada e está pendente de aprovação.',
        tipo='RESERVA_CRIADA',
        link='/reservas/',
    )


def notificar_reserva_aprovada(agendamento):
    criar_notificacao(
        destinatario=agendamento.usuario,
        titulo='Reserva aprovada',
        mensagem=f'Sua reserva para a sala "{agendamento.sala.nome}" em {agendamento.data_inicio.strftime("%d/%m/%Y")} às {agendamento.horario.strftime("%H:%M")} foi aprovada.',
        tipo='RESERVA_APROVADA',
        link='/reservas/',
    )


def notificar_reserva_rejeitada(agendamento):
    criar_notificacao(
        destinatario=agendamento.usuario,
        titulo='Reserva rejeitada',
        mensagem=f'Sua reserva para a sala "{agendamento.sala.nome}" em {agendamento.data_inicio.strftime("%d/%m/%Y")} às {agendamento.horario.strftime("%H:%M")} foi rejeitada.',
        tipo='RESERVA_REJEITADA',
        link='/reservas/',
    )


def notificar_reserva_cancelada(agendamento):
    from django.contrib.auth.models import User
    admins = User.objects.filter(is_staff=True, is_active=True)
    for admin in admins:
        criar_notificacao(
            destinatario=admin,
            titulo='Reserva cancelada',
            mensagem=f'{agendamento.usuario.get_full_name() or agendamento.usuario.username} cancelou a reserva da sala "{agendamento.sala.nome}" para {agendamento.data_inicio.strftime("%d/%m/%Y")}.',
            tipo='RESERVA_CANCELADA',
            link='/gerenciar/',
        )


def notificar_manutencao_criada(solicitacao):
    from django.contrib.auth.models import User
    autor = solicitacao.solicitante.get_full_name() or solicitacao.solicitante.username

    for admin in User.objects.filter(is_staff=True, is_active=True):
        criar_notificacao(
            destinatario=admin,
            titulo='Nova solicitação de manutenção',
            mensagem=(
                f'{autor} relatou um problema de {solicitacao.get_categoria_display().lower()} '
                f'em "{solicitacao.local}".'
            ),
            tipo='MANUTENCAO_CRIADA',
            link=solicitacao.get_absolute_url(),
        )

    criar_notificacao(
        destinatario=solicitacao.solicitante,
        titulo='Solicitação registrada',
        mensagem=(
            f'Sua solicitação de manutenção para "{solicitacao.local}" foi registrada '
            f'e está aguardando análise.'
        ),
        tipo='MANUTENCAO_CRIADA',
        link=solicitacao.get_absolute_url(),
    )


def notificar_manutencao_atualizada(solicitacao, observacao=''):
    """Avisa o solicitante de qualquer mudança de status.

    Quando a solicitação é resolvida usa um tipo próprio, para a
    notificação de conclusão se destacar das demais.
    """
    resolvida = solicitacao.status == solicitacao.RESOLVIDA

    if resolvida:
        titulo = 'Manutenção concluída'
        mensagem = f'O problema relatado em "{solicitacao.local}" foi resolvido.'
        tipo = 'MANUTENCAO_RESOLVIDA'
    else:
        titulo = 'Solicitação atualizada'
        mensagem = (
            f'Sua solicitação para "{solicitacao.local}" agora está com o status '
            f'"{solicitacao.get_status_display()}".'
        )
        tipo = 'MANUTENCAO_ATUALIZADA'

    if observacao:
        mensagem = f'{mensagem} Observação: {observacao}'

    criar_notificacao(
        destinatario=solicitacao.solicitante,
        titulo=titulo,
        mensagem=mensagem,
        tipo=tipo,
        link=solicitacao.get_absolute_url(),
    )


def notificar_lembrete(usuario, agendamento):
    criar_notificacao(
        destinatario=usuario,
        titulo='Lembrete de reserva',
        mensagem=f'Você tem uma reserva para a sala "{agendamento.sala.nome}" em {agendamento.data_inicio.strftime("%d/%m/%Y")} às {agendamento.horario.strftime("%H:%M")}.',
        tipo='LEMBRETE',
        link='/reservas/',
    )
