"""Quem pode avaliar um espaço, quando, e como sai a média."""

from datetime import timedelta

from django.db.models import Avg, Count
from django.urls import reverse
from django.utils import timezone

from avaliacoes.models import Avaliacao
from bedesk.models import Sala
from notificacoes.models import Notificacao

# Faixa fora da grade (reserva antiga) não tem fim declarado; 45 minutos é a
# duração de todas as faixas da grade atual.
DURACAO_PADRAO = timedelta(minutes=45)

# Quantas avaliações um espaço precisa ter para disputar melhor e pior. Com
# uma nota só, a média é a opinião de uma pessoa — e o painel apontaria a
# manutenção para o espaço errado.
MINIMO_PARA_RANKING = 3

# Até quantos dias depois do uso ainda vale lembrar. Mais que isso, a pessoa
# já não lembra do que achou do espaço.
DIAS_DE_LEMBRETE = 7


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


def reservas_usadas_sem_avaliacao(usuario=None, desde=None):
    """Reservas que já foram usadas e continuam sem avaliação.

    Sem `usuario`, varre o sistema inteiro — é assim que o lembrete encontra
    quem avisar. `desde` corta o passado distante: não faz sentido lembrar
    hoje de um uso de três meses atrás.
    """
    from bedesk.models import Agendamento

    candidatas = Agendamento.objects.filter(
        status='APROVADO',
        eventos__isnull=True,
        avaliacao__isnull=True,
        data_inicio__isnull=False,
    )
    if usuario is not None:
        candidatas = candidatas.filter(usuario=usuario)
    if desde is not None:
        candidatas = candidatas.filter(data_inicio__gte=desde)

    candidatas = candidatas.select_related('sala', 'usuario').order_by('-data_inicio')

    agora = timezone.localtime()
    return [r for r in candidatas if (fim_da_reserva(r) or agora) <= agora]


def reservas_avaliaveis(usuario):
    """Reservas já usadas por essa pessoa e ainda sem avaliação."""
    return reservas_usadas_sem_avaliacao(usuario=usuario)


def link_para_avaliar(reserva):
    """O endereço do formulário daquela reserva.

    Mora aqui porque é o mesmo valor usado para mandar o lembrete e para
    saber se ele já foi mandado: se os dois calculassem o link por conta
    própria, um ajuste em um deles faria a pessoa receber o lembrete de novo.
    """
    return reverse('avaliar_reserva', args=[reserva.pk])


def reservas_a_lembrar(dias=None):
    """Usos sem avaliação, dentro da janela, que ainda não receberam lembrete."""
    dias = DIAS_DE_LEMBRETE if dias is None else dias
    desde = timezone.localtime() - timedelta(days=dias)
    candidatas = reservas_usadas_sem_avaliacao(desde=desde)
    if not candidatas:
        return []

    # O próprio lembrete é o registro de que ele já foi enviado: as
    # notificações do BE-Desk nunca são apagadas, só marcadas como lidas.
    links = {link_para_avaliar(reserva): reserva for reserva in candidatas}
    ja_lembradas = set(
        Notificacao.objects.filter(tipo='LEMBRETE', link__in=list(links)).values_list(
            'link', flat=True
        )
    )
    return [reserva for link, reserva in links.items() if link not in ja_lembradas]


def enviar_lembretes(dias=None):
    """Manda o lembrete de avaliação e devolve quantos foram enviados."""
    from notificacoes.services.notificar import notificar_lembrete_de_avaliacao

    reservas = reservas_a_lembrar(dias)
    for reserva in reservas:
        notificar_lembrete_de_avaliacao(reserva, link_para_avaliar(reserva))
    return reservas


def _arredondar(valor):
    return round(valor, 1) if valor is not None else None


def medias_por_espaco():
    """Todos os espaços com as suas médias, da melhor nota para a pior.

    Espaço sem nenhuma avaliação entra na lista com `media` nula e vai para o
    fim — some da tabela seria pior, porque "ainda não avaliado" é uma
    informação útil para quem administra.

    Cada linha diz, em `no_ranking`, se já tem avaliações suficientes para
    entrar na disputa de melhor e pior.
    """
    # Agregar a partir das avaliações, e não dos espaços: partindo de Sala, o
    # LEFT JOIN percorre todas as reservas — tabela que cresce para sempre —
    # antes de agrupar. Medido em 80 mil reservas, a diferença foi de 0,9 ms
    # para 21 ms, e esta consulta roda na lista de locais de todo usuário.
    resumo = {
        linha['reserva__sala_id']: linha
        for linha in Avaliacao.objects.values('reserva__sala_id').annotate(
            media=Avg('nota'),
            total=Count('id'),
            media_limpeza=Avg('limpeza'),
            media_estrutura=Avg('estrutura'),
            media_organizacao=Avg('organizacao'),
            media_conservacao=Avg('conservacao'),
        )
    }

    linhas = []
    for espaco in Sala.objects.all():
        dados = resumo.get(espaco.pk)
        total = dados['total'] if dados else 0
        linhas.append({
            'sala_id': espaco.pk,
            'nome': espaco.nome,
            'media': _arredondar(dados['media']) if dados else None,
            'total': total,
            'media_limpeza': _arredondar(dados['media_limpeza']) if dados else None,
            'media_estrutura': _arredondar(dados['media_estrutura']) if dados else None,
            'media_organizacao': _arredondar(dados['media_organizacao']) if dados else None,
            'media_conservacao': _arredondar(dados['media_conservacao']) if dados else None,
            'no_ranking': total >= MINIMO_PARA_RANKING,
        })

    # Melhor nota primeiro; sem nota vai para o fim; empate desempata pelo nome.
    linhas.sort(key=lambda linha: (
        linha['media'] is None,
        -(linha['media'] or 0),
        linha['nome'],
    ))
    return linhas


def espacos_no_ranking(medias=None):
    """Só os espaços com avaliações suficientes, da melhor nota para a pior."""
    linhas = medias_por_espaco() if medias is None else medias
    return [linha for linha in linhas if linha['no_ranking']]


def melhor_e_pior(medias=None):
    """(melhor, pior) entre os espaços que entram no ranking.

    Com um espaço só, ele é o melhor e não há pior: dizer que o único espaço
    avaliado é também o pior não informa nada.
    """
    ranking = espacos_no_ranking(medias)
    if not ranking:
        return (None, None)
    return (ranking[0], ranking[-1] if len(ranking) > 1 else None)


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
        linha['sala_id']: (linha['media'], linha['total'])
        for linha in medias_por_espaco()
    }
