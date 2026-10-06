"""Manda o lembrete de avaliação para quem usou um espaço e não avaliou.

Feito para rodar por cron no servidor, uma vez por dia:

    0 19 * * *  cd /app && python manage.py lembrar_de_avaliar

Rodar várias vezes no mesmo dia não duplica nada: cada reserva só recebe um
lembrete, e o próprio lembrete é o registro disso.
"""

from django.core.management.base import BaseCommand

from avaliacoes.services import DIAS_DE_LEMBRETE, enviar_lembretes, reservas_a_lembrar


class Command(BaseCommand):
    help = 'Lembra quem usou um espaço de avaliá-lo.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias',
            type=int,
            default=DIAS_DE_LEMBRETE,
            help=f'Quantos dias de uso olhar para trás (padrão: {DIAS_DE_LEMBRETE}).',
        )
        parser.add_argument(
            '--simular',
            action='store_true',
            help='Mostra quem receberia o lembrete, sem enviar nada.',
        )

    def handle(self, *args, **opcoes):
        dias = opcoes['dias']

        if opcoes['simular']:
            reservas = reservas_a_lembrar(dias)
            for reserva in reservas:
                self.stdout.write(
                    f'  {reserva.usuario.get_full_name() or reserva.usuario.username}'
                    f' — {reserva.sala.nome}, {reserva.data_inicio:%d/%m/%Y} {reserva.horario:%H:%M}'
                )
            self.stdout.write(f'{len(reservas)} lembrete(s) seriam enviados (nada foi gravado).')
            return

        reservas = enviar_lembretes(dias)
        self.stdout.write(self.style.SUCCESS(f'{len(reservas)} lembrete(s) enviados.'))
