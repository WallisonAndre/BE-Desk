"""Completa a ocupação da grade dos eventos criados pela regra antiga.

Até a mudança da regra, o evento só ocupava a faixa da grade que começava
dentro da sua janela: um evento das 14:00 às 16:00 não ocupava a faixa
13:45–14:30, que continuava reservável com o evento em andamento. A regra
nova ocupa toda faixa que se sobrepõe à janela, mas os eventos já
cadastrados guardam a ocupação antiga até alguém editá-los.

Para cada evento programado que ainda não terminou, cria as faixas que
faltam a partir de hoje. Faixa que já tem reserva aprovada não é ocupada,
para não gerar duas ocupações no mesmo horário: o caso sai listado no
migrate para ser resolvido à mão.

As faixas estão copiadas aqui de propósito. A migração precisa produzir o
mesmo resultado mesmo que a grade mude depois.
"""

from datetime import datetime, time, timedelta

from django.db import migrations
from django.utils import timezone

FAIXAS = [
    (time(7, 0), time(7, 45)),
    (time(7, 45), time(8, 30)),
    (time(8, 50), time(9, 35)),
    (time(9, 35), time(10, 20)),
    (time(10, 30), time(11, 15)),
    (time(11, 15), time(12, 0)),
    (time(13, 0), time(13, 45)),
    (time(13, 45), time(14, 30)),
    (time(14, 50), time(15, 35)),
    (time(15, 35), time(16, 20)),
    (time(16, 30), time(17, 15)),
    (time(17, 15), time(18, 0)),
]


def completar_ocupacao(apps, schema_editor):
    Evento = apps.get_model('eventos', 'Evento')
    Agendamento = apps.get_model('bedesk', 'Agendamento')
    hoje = timezone.localdate()

    for evento in Evento.objects.filter(status='PROGRAMADO', data_fim__gte=hoje):
        ja_ocupadas = {
            (timezone.localtime(a.data_inicio).date(), a.horario)
            for a in evento.agendamentos.all()
            if a.data_inicio
        }
        dia = max(evento.data_inicio, hoje)
        while dia <= evento.data_fim:
            for inicio, fim in FAIXAS:
                if not (inicio < evento.horario_fim and fim > evento.horario_inicio):
                    continue
                if (dia, inicio) in ja_ocupadas:
                    continue
                reservada = Agendamento.objects.filter(
                    sala_id=evento.sala_id,
                    data_inicio__date=dia,
                    horario=inicio,
                    status='APROVADO',
                    eventos__isnull=True,
                ).exists()
                if reservada:
                    print(
                        f'\n  eventos.0003: {dia:%d/%m/%Y} às {inicio:%H:%M}, evento #{evento.pk} '
                        f'"{evento.nome}": a faixa já tem reserva aprovada e não foi ocupada.'
                    )
                    continue
                evento.agendamentos.add(
                    Agendamento.objects.create(
                        usuario_id=evento.responsavel_id,
                        sala_id=evento.sala_id,
                        nome=evento.nome,
                        motivo=f'Evento: {evento.nome}',
                        horario=inicio,
                        data_inicio=timezone.make_aware(datetime.combine(dia, inicio)),
                        status='APROVADO',
                    )
                )
            dia += timedelta(days=1)


class Migration(migrations.Migration):

    dependencies = [
        ('eventos', '0002_remove_evento_vagas'),
        ('bedesk', '0007_sala_foto'),
    ]

    operations = [
        migrations.RunPython(completar_ocupacao, migrations.RunPython.noop),
    ]
