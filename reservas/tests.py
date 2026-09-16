"""Grade de horários da sala."""
from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bedesk.models import Agendamento, Sala
from django.core.exceptions import ValidationError

from reservas.models import HorarioFixo

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


class PedidoDeReservaTests(TestCase):
    """Vários alunos podem pedir o mesmo horário; aprovado é que ocupa."""

    def setUp(self):
        self.aluno = User.objects.create_user('aluno', password='x')
        self.outro = User.objects.create_user('outro', password='x')
        self.sala = Sala.objects.create(nome='Quadra')
        self.dia = date.today() + timedelta(days=1)
        while self.dia.weekday() >= 5:
            self.dia += timedelta(days=1)

    def reserva(self, usuario, hora, status):
        return Agendamento.objects.create(
            usuario=usuario, sala=self.sala, nome='Treino', motivo='treino', horario=hora,
            data_inicio=timezone.make_aware(datetime.combine(self.dia, hora)), status=status,
        )

    def pedir(self, hora):
        self.client.force_login(self.outro)
        return self.client.post(reverse('agendar_sala'), {
            'nome': 'Treino do outro', 'sala': self.sala.pk, 'motivo': 'treino',
            'horario': hora.strftime('%H:%M'), 'data_inicio': self.dia.isoformat(),
        })

    def pedidos_do_outro(self):
        return Agendamento.objects.filter(usuario=self.outro).count()

    def test_horario_livre_aceita_pedido(self):
        self.pedir(time(7, 0))
        self.assertEqual(self.pedidos_do_outro(), 1)

    def test_pedido_pendente_de_outra_pessoa_nao_impede(self):
        self.reserva(self.aluno, time(7, 45), 'PENDENTE')
        self.pedir(time(7, 45))
        self.assertEqual(self.pedidos_do_outro(), 1)
        self.assertEqual(
            Agendamento.objects.filter(horario=time(7, 45), status='PENDENTE').count(), 2
        )

    def test_reserva_aprovada_impede_o_pedido(self):
        self.reserva(self.aluno, time(8, 50), 'APROVADO')
        resp = self.pedir(time(8, 50))
        self.assertEqual(self.pedidos_do_outro(), 0)
        self.assertContains(resp, 'já tem uma reserva aprovada')

    def test_reserva_rejeitada_nao_impede(self):
        self.reserva(self.aluno, time(9, 35), 'REJEITADO')
        self.pedir(time(9, 35))
        self.assertEqual(self.pedidos_do_outro(), 1)


class AprovacaoDeVariosPedidosTests(TestCase):
    """Vários pedidos no mesmo horário, mas só uma aprovação."""

    def setUp(self):
        self.admin = User.objects.create_user('admin', password='x', is_staff=True)
        self.aluno = User.objects.create_user('aluno', password='x')
        self.outro = User.objects.create_user('outro', password='x')
        self.sala = Sala.objects.create(nome='Quadra')
        self.hora = time(7, 45)
        self.dia = date.today() + timedelta(days=1)
        while self.dia.weekday() >= 5:
            self.dia += timedelta(days=1)

    def pedido(self, usuario):
        return Agendamento.objects.create(
            usuario=usuario, sala=self.sala, nome=f'Treino de {usuario.username}',
            motivo='treino', horario=self.hora,
            data_inicio=timezone.make_aware(datetime.combine(self.dia, self.hora)),
            status='PENDENTE',
        )

    def aprovar(self, agendamento):
        self.client.force_login(self.admin)
        return self.client.post(reverse('aprovar_reserva', args=[agendamento.pk]))

    def aprovadas(self):
        return Agendamento.objects.filter(
            sala=self.sala, data_inicio__date=self.dia, horario=self.hora, status='APROVADO'
        ).count()

    def test_aprovar_o_segundo_pedido_do_mesmo_horario_e_barrado(self):
        primeiro, segundo = self.pedido(self.aluno), self.pedido(self.outro)

        self.aprovar(primeiro)
        primeiro.refresh_from_db()
        self.assertEqual(primeiro.status, 'APROVADO')

        resp = self.aprovar(segundo)
        segundo.refresh_from_db()
        self.assertEqual(segundo.status, 'PENDENTE')
        self.assertEqual(self.aprovadas(), 1)
        self.assertIn(
            'já está ocupada',
            ' '.join(str(m) for m in get_messages(resp.wsgi_request)),
        )

    def test_recusar_o_segundo_libera_o_horario_para_ele_depois(self):
        primeiro, segundo = self.pedido(self.aluno), self.pedido(self.outro)
        self.aprovar(primeiro)

        self.client.force_login(self.admin)
        self.client.post(reverse('rejeitar_reserva', args=[primeiro.pk]))

        self.aprovar(segundo)
        segundo.refresh_from_db()
        self.assertEqual(segundo.status, 'APROVADO')
        self.assertEqual(self.aprovadas(), 1)

    def test_aprovacao_por_ajax_do_segundo_devolve_409(self):
        primeiro, segundo = self.pedido(self.aluno), self.pedido(self.outro)
        self.aprovar(primeiro)

        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse('aprovar_reserva', args=[segundo.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp.status_code, 409)
        self.assertFalse(resp.json()['success'])
        self.assertEqual(self.aprovadas(), 1)


class HorarioFixoModeloTests(TestCase):
    def setUp(self):
        self.sala = Sala.objects.create(nome='Ginásio')

    def criar(self, inicio, fim, dia=HorarioFixo.SEGUNDA, descricao='Treino de futsal'):
        horario = HorarioFixo(
            sala=self.sala, dia_semana=dia, horario_inicio=inicio, horario_fim=fim,
            descricao=descricao,
        )
        horario.full_clean()
        horario.save()
        return horario

    def test_aceita_horario_dentro_da_grade(self):
        horario = self.criar(time(7, 0), time(8, 30))
        self.assertEqual(horario.periodo, '07:00 às 08:30')
        self.assertEqual(str(horario), 'Treino de futsal — Ginásio, Segunda-feira')

    def test_recusa_termino_antes_do_inicio(self):
        with self.assertRaises(ValidationError) as erro:
            self.criar(time(10, 0), time(9, 0))
        self.assertIn('horario_fim', erro.exception.message_dict)

    def test_recusa_horario_fora_da_grade(self):
        with self.assertRaises(ValidationError) as erro:
            self.criar(time(19, 0), time(21, 0))
        self.assertIn('dentro da grade', str(erro.exception))

    def test_recusa_dia_de_fim_de_semana(self):
        with self.assertRaises(ValidationError) as erro:
            self.criar(time(8, 0), time(9, 0), dia=5)
        self.assertIn('dia_semana', erro.exception.message_dict)

    def test_nao_repete_mesma_sala_dia_e_inicio(self):
        self.criar(time(7, 0), time(8, 30))
        with self.assertRaises(ValidationError) as erro:
            self.criar(time(7, 0), time(9, 35), descricao='Outro treino')
        self.assertIn('já existe', str(erro.exception).lower())

    def test_mesma_sala_e_horario_em_outro_dia_e_permitido(self):
        self.criar(time(7, 0), time(8, 30))
        self.criar(time(7, 0), time(8, 30), dia=2)
        self.assertEqual(HorarioFixo.objects.count(), 2)


class HorarioFixoNaGradeTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user('aluno', password='x')
        self.sala = Sala.objects.create(nome='Ginásio')
        # Segunda-feira da próxima semana, para a grade sempre encontrá-la.
        hoje = date.today()
        self.segunda = hoje - timedelta(days=hoje.weekday()) + timedelta(days=7)
        self.fixo = HorarioFixo.objects.create(
            sala=self.sala, dia_semana=HorarioFixo.SEGUNDA, horario_inicio=time(7, 0),
            horario_fim=time(8, 30), descricao='Treino de futsal',
        )

    def grade(self):
        self.client.force_login(self.usuario)
        resp = self.client.get(
            reverse('detalhe_sala', args=[self.sala.nome]), {'foco': self.segunda.isoformat()}
        )
        self.assertEqual(resp.status_code, 200)
        return resp

    def celulas_fixas(self, resp):
        return [
            (linha['hora_para_link'], indice)
            for linha in resp.context['tabela_horarios'] if linha['tipo'] == 'hora'
            for indice, celula in enumerate(linha['celulas']) if celula['horario_fixo']
        ]

    def test_ocupa_todas_as_faixas_da_janela_na_segunda(self):
        self.assertEqual(self.celulas_fixas(self.grade()), [('07:00', 0), ('07:45', 0)])

    def test_aparece_identificado_e_sem_botao_de_reservar(self):
        html = self.grade().content.decode()
        self.assertIn('Treino de futsal', html)
        self.assertIn('badge-fixo', html)
        self.assertIn('Horário fixo', html)

    def test_se_repete_na_semana_seguinte_sem_recadastrar(self):
        self.client.force_login(self.usuario)
        proxima = self.segunda + timedelta(days=7)
        resp = self.client.get(
            reverse('detalhe_sala', args=[self.sala.nome]), {'foco': proxima.isoformat()}
        )
        self.assertEqual(self.celulas_fixas(resp), [('07:00', 0), ('07:45', 0)])

    def test_remover_libera_a_grade(self):
        self.fixo.delete()
        self.assertEqual(self.celulas_fixas(self.grade()), [])

    def test_editar_move_a_ocupacao(self):
        self.fixo.dia_semana = 2
        self.fixo.horario_inicio = time(13, 0)
        self.fixo.horario_fim = time(13, 45)
        self.fixo.save()
        self.assertEqual(self.celulas_fixas(self.grade()), [('13:00', 2)])

    def test_nao_aparece_em_outra_sala(self):
        outra = Sala.objects.create(nome='Quadra Coberta')
        self.client.force_login(self.usuario)
        resp = self.client.get(
            reverse('detalhe_sala', args=[outra.nome]), {'foco': self.segunda.isoformat()}
        )
        self.assertEqual(self.celulas_fixas(resp), [])
