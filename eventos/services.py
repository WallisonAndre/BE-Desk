"""Integração entre eventos e o sistema de reservas.

O evento não guarda a ocupação por conta própria: ele cria agendamentos
aprovados nos horários que usa. Assim ele aparece na grade da sala junto
das reservas comuns e o mesmo horário deixa de ser reservável, sem
precisar duplicar a lógica de conflito em dois lugares.
"""

from datetime import datetime, timedelta

from django.utils import timezone

from bedesk.models import Agendamento
from reservas.views.salas import HORARIOS_ESTRUTURA

# Slots fixos da grade (07:00, 07:45, ...), ignorando intervalos.
SLOTS = [
    datetime.strptime(item['inicio'], '%H:%M').time()
    for item in HORARIOS_ESTRUTURA
    if item['tipo'] == 'hora'
]


def _dias_do_evento(evento):
    dia = evento.data_inicio
    while dia <= evento.data_fim:
        yield dia
        dia += timedelta(days=1)


def slots_ocupados(evento):
    """Pares (data, hora) da grade que o evento cobre.

    Um slot entra se o seu início cai dentro da janela do evento — um
    evento das 14h às 16h ocupa 14:00, 14:50, 15:35 e assim por diante.
    """
    pares = []
    for dia in _dias_do_evento(evento):
        for slot in SLOTS:
            if evento.horario_inicio <= slot < evento.horario_fim:
                pares.append((dia, slot))
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
