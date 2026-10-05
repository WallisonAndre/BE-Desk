"""Quem pode avaliar um espaço, quando, e como sai a média."""

from datetime import timedelta

from django.db.models import Avg, Count
from django.utils import timezone

from avaliacoes.models import Avaliacao

# Faixa fora da grade (reserva antiga) não tem fim declarado; 45 minutos é a
# duração de todas as faixas da grade atual.
DURACAO_PADRAO = timedelta(minutes=45)

# Até esta nota, a avaliação é tratada como reclamação e o staff é avisado na
# hora. Acima dela, o espaço entrou no painel e basta.
NOTA_QUE_AVISA_O_STAFF = 2


def fim_da_reserva(reserva):
    """Instante em que o uso do espaço termina.

    A grade fica em `reservas.views.salas`; o import é local porque aquele
    módulo já carrega este app pela cadeia de views.
    """
    from reservas.views.salas import FAIXAS_HORARIO

    if not reserva.data_inicio:
        return None

    inicio = timezone.localtime(reserva.data_inicio)
    for faixa_inicio, faixa_fim in FAIXAS_HORARIO:
        if faixa_inicio == reserva.horario:
            return inicio.replace(
                hour=faixa_fim.hour, minute=faixa_fim.minute, second=0, microsecond=0
            )
    return inicio + DURACAO_PADRAO


def motivo_para_nao_avaliar(reserva, usuario):
    """Por que esta pessoa não pode avaliar esta reserva — ou `None` se pode.

    A avaliação é sobre uso: só avalia quem reservou, se a reserva foi
    aprovada e o horário já passou. Uma reserva rende uma avaliação só.
    """
    if reserva.usuario_id != usuario.pk:
        return 'Esta reserva não é sua.'
    if reserva.eventos.exists():
        return 'Esta faixa pertence a um evento, não a uma reserva sua.'
    if reserva.status != 'APROVADO':
        return 'Só é possível avaliar reservas aprovadas.'

    fim = fim_da_reserva(reserva)
    if fim is None or fim > timezone.localtime():
        return 'O horário ainda não terminou. A avaliação abre depois do uso.'

    if Avaliacao.objects.filter(reserva=reserva).exists():
        return 'Você já avaliou esta reserva.'
    return None


def pode_avaliar(reserva, usuario):
    return motivo_para_nao_avaliar(reserva, usuario) is None


def reservas_avaliaveis(usuario):
    """Reservas já usadas por essa pessoa e ainda sem avaliação."""
    from bedesk.models import Agendamento

    candidatas = (
        Agendamento.objects.filter(
            usuario=usuario,
            status='APROVADO',
            eventos__isnull=True,
            avaliacao__isnull=True,
            data_inicio__isnull=False,
        )
        .select_related('sala')
        .order_by('-data_inicio')
    )
    agora = timezone.localtime()
    return [r for r in candidatas if (fim_da_reserva(r) or agora) <= agora]


def medias_por_espaco():
    """Média e quantidade de avaliações de cada espaço, da melhor para a pior."""
    return (
        Avaliacao.objects.values('reserva__sala__id', 'reserva__sala__nome')
        .annotate(
            media=Avg('nota'),
            total=Count('id'),
            media_limpeza=Avg('limpeza'),
            media_estrutura=Avg('estrutura'),
            media_organizacao=Avg('organizacao'),
            media_conservacao=Avg('conservacao'),
        )
        .order_by('-media', 'reserva__sala__nome')
    )


def media_do_espaco(sala):
    """(média, total) das avaliações de um espaço. Sem avaliação, (None, 0)."""
    resumo = Avaliacao.objects.filter(reserva__sala=sala).aggregate(
        media=Avg('nota'), total=Count('id')
    )
    media = resumo['media']
    return (round(media, 1) if media is not None else None, resumo['total'])


def mapa_de_medias():
    """{sala_id: (média, total)} para listar vários espaços sem uma consulta por espaço."""
    return {
        linha['reserva__sala__id']: (round(linha['media'], 1), linha['total'])
        for linha in medias_por_espaco()
    }
