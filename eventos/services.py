"""Integração entre eventos e o sistema de reservas.

O evento não guarda a ocupação por conta própria: ele cria agendamentos
aprovados nos horários da grade que usa. Assim ele aparece na grade da sala
junto das reservas comuns, e o mesmo horário deixa de ser reservável sem
duplicar a lógica de conflito das reservas.

Entre dois eventos, porém, o conflito é conferido pela janela real de
horário, e não pelas faixas da grade. Dois eventos colados (08:00–10:00 e
10:00–12:00) encostam na mesma faixa sem se sobrepor, e dois eventos depois
das 18:00 não ocupam faixa nenhuma, mas podem se sobrepor de verdade.
"""

from datetime import datetime, timedelta

from django.utils import timezone

from bedesk.models import Agendamento
from eventos.models import Evento
from reservas.views.salas import FAIXAS_HORARIO, horarios_fixos_sobrepostos


def _dias_do_evento(evento):
    dia = evento.data_inicio
    while dia <= evento.data_fim:
        yield dia
        dia += timedelta(days=1)


def slots_ocupados(evento):
    """Pares (data, hora de início) dos horários da grade que o evento toca.

    Um horário entra quando qualquer trecho dele cai dentro da janela do
    evento. Um evento das 14:00 às 16:00 ocupa 13:45, 14:50 e 15:35: o
    horário das 13:45 começa antes, mas só termina às 14:30, com o evento já
    em andamento. Olhar apenas o início deixava esse trecho reservável, e um
    evento curto entre dois inícios — 14:00 às 14:40 — não ocupava nada.
    """
    pares = []
    for dia in _dias_do_evento(evento):
        for inicio, fim in FAIXAS_HORARIO:
            if inicio < evento.horario_fim and fim > evento.horario_inicio:
                pares.append((dia, inicio))
    return pares


def eventos_sobrepostos(evento, ignorar_evento=None):
    """Eventos programados na mesma sala cuja janela real cruza a do evento.

    As janelas se cruzam quando os períodos de datas se cruzam e, no dia, uma
    começa antes de a outra terminar. Encostar não é cruzar: um evento que
    termina às 10:00 não colide com outro que começa às 10:00.
    """
    eventos = Evento.objects.filter(
        sala=evento.sala,
        status=Evento.PROGRAMADO,
        data_inicio__lte=evento.data_fim,
        data_fim__gte=evento.data_inicio,
        horario_inicio__lt=evento.horario_fim,
        horario_fim__gt=evento.horario_inicio,
    )
    if ignorar_evento is not None and ignorar_evento.pk:
        eventos = eventos.exclude(pk=ignorar_evento.pk)
    return list(eventos.order_by('data_inicio', 'horario_inicio'))


def reservas_sobrepostas(evento):
    """Reservas aprovadas nas faixas da grade que o evento vai ocupar.

    Faixas geradas por eventos não entram: entre eventos, o conflito é
    conferido pela janela real, em eventos_sobrepostos.
    """
    pares = set(slots_ocupados(evento))
    if not pares:
        return []
    candidatas = Agendamento.objects.filter(
        sala=evento.sala,
        status='APROVADO',
        eventos__isnull=True,
        data_inicio__date__range=(evento.data_inicio, evento.data_fim),
        horario__in={hora for _, hora in pares},
    ).order_by('data_inicio', 'horario')
    return [
        reserva for reserva in candidatas
        if (timezone.localtime(reserva.data_inicio).date(), reserva.horario) in pares
    ]


def buscar_conflitos(evento, ignorar_evento=None):
    """Descrições do que impede o evento de ocupar a sala no horário pedido."""
    conflitos = [
        f'pelo evento "{outro.nome}" ({_periodo(outro)})'
        for outro in eventos_sobrepostos(evento, ignorar_evento)
    ]
    conflitos += [
        f'pelo horário fixo "{fixo.descricao}" '
        f'(toda {fixo.get_dia_semana_display().lower()}, {fixo.periodo})'
        for fixo in horarios_fixos_sobrepostos(
            evento.sala,
            list(_dias_do_evento(evento)),
            evento.horario_inicio,
            evento.horario_fim,
        )
    ]
    conflitos += [
        f'pela reserva "{reserva.nome}" em {timezone.localtime(reserva.data_inicio):%d/%m} '
        f'às {reserva.horario:%H:%M}'
        for reserva in reservas_sobrepostas(evento)
    ]
    return conflitos


def _periodo(evento):
    if evento.data_inicio == evento.data_fim:
        datas = f'{evento.data_inicio:%d/%m}'
    else:
        datas = f'{evento.data_inicio:%d/%m} a {evento.data_fim:%d/%m}'
    return f'{datas}, {evento.horario_inicio:%H:%M}–{evento.horario_fim:%H:%M}'


def reservar_espaco(evento):
    """Cria (ou recria) os agendamentos que bloqueiam a grade."""
    liberar_espaco(evento)

    criados = []
    for dia, slot in slots_ocupados(evento):
        criados.append(
            Agendamento.objects.create(
                usuario=evento.responsavel,
                sala=evento.sala,
                nome=evento.nome,
                motivo=f'Evento: {evento.nome}',
                horario=slot,
                # Aware: com USE_TZ ligado, datetime ingênuo dispara aviso
                # e pode deslocar o dia na conversão.
                data_inicio=timezone.make_aware(datetime.combine(dia, slot)),
                status='APROVADO',
            )
        )

    evento.agendamentos.set(criados)
    return criados


def liberar_espaco(evento):
    """Remove os agendamentos do evento, devolvendo os horários à grade."""
    if not evento.pk:
        return
    antigos = list(evento.agendamentos.all())
    evento.agendamentos.clear()
    Agendamento.objects.filter(pk__in=[a.pk for a in antigos]).delete()
