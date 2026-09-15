"""Grade de horários da sala."""
from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bedesk.models import Agendamento, Sala

User = get_user_model()


class GradeDaSalaTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user('aluno', password='x')
        self.sala = Sala.objects.create(nome='Quadra')
        self.dia = date.today() + timedelta(days=1)
        while self.dia.weekday() >= 5:
            self.dia += timedelta(days=1)

    def reserva(self, nome, hora, status):
        return Agendamento.objects.create(
            usuario=self.usuario, sala=self.sala, nome=nome, motivo='treino', horario=hora,
            data_inicio=timezone.make_aware(datetime.combine(self.dia, hora)), status=status,
        )

    def grade(self):
        self.client.force_login(self.usuario)
        resp = self.client.get(
            reverse('detalhe_sala', args=[self.sala.nome]), {'foco': self.dia.isoformat()}
        )
        self.assertEqual(resp.status_code, 200)
        return [
            celula['agendamento']
            for linha in resp.context['tabela_horarios'] if linha['tipo'] == 'hora'
            for celula in linha['celulas'] if celula['agendamento']
        ]

    def test_reserva_aprovada_aparece_na_grade(self):
        aprovada = self.reserva('Treino aprovado', time(7, 0), 'APROVADO')
        self.assertEqual(self.grade(), [aprovada])

    def test_reserva_pendente_nao_aparece_na_grade(self):
        self.reserva('Treino pendente', time(7, 45), 'PENDENTE')
        self.assertEqual(self.grade(), [])

    def test_reserva_rejeitada_nao_aparece_na_grade(self):
        self.reserva('Treino rejeitado', time(8, 50), 'REJEITADO')
        self.assertEqual(self.grade(), [])

    def test_pendente_aparece_depois_de_aprovada(self):
        pedido = self.reserva('Treino', time(9, 35), 'PENDENTE')
        self.assertEqual(self.grade(), [])
        pedido.status = 'APROVADO'
        pedido.save()
        self.assertEqual(self.grade(), [pedido])
