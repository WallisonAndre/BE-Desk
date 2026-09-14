"""Integração entre eventos e o sistema de reservas.

O evento não guarda a ocupação por conta própria: ele cria agendamentos
aprovados nos horários que usa. Assim ele aparece na grade da sala junto
das reservas comuns e o mesmo horário deixa de ser reservável, sem
precisar duplicar a lógica de conflito em dois lugares.
"""

from datetime import datetime, timedelta

from django.utils import timezone

from bedesk.models import Agendamento
from reservas.views.salas import FAIXAS_HORARIO


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


def buscar_conflitos(evento, ignorar_evento=None):
    """Agendamentos aprovados que colidem com os horários do evento."""
    pares = slots_ocupados(evento)
    if not pares:
        return []

    conflitos = []
    for dia, slot in pares:
        qs = Agendamento.objects.filter(
            sala=evento.sala,
            data_inicio__date=dia,
            horario=slot,
            status='APROVADO',
        )
        if ignorar_evento and ignorar_evento.pk:
            qs = qs.exclude(pk__in=ignorar_evento.agendamentos.values_list('pk', flat=True))
        conflito = qs.first()
        if conflito:
            conflitos.append(conflito)
    return conflitos


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
