"""Grade de horários da sala."""
from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bedesk.models import Agendamento, Sala
from notificacoes.models import Notificacao
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
        segundo.refresh_from_db()
        self.assertEqual(primeiro.status, 'APROVADO')
        # aprovar o primeiro já recusa o concorrente (issue #22)
        self.assertEqual(segundo.status, 'REJEITADO')

        # e insistir nele continua barrado: o horário está ocupado
        resp = self.aprovar(segundo)
        segundo.refresh_from_db()
        self.assertEqual(segundo.status, 'REJEITADO')
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


class HorarioFixoBloqueiaTests(TestCase):
    """O horário fixo é respeitado no pedido, na aprovação e no evento."""

    def setUp(self):
        self.admin = User.objects.create_user('admin', password='x', is_staff=True)
        self.aluno = User.objects.create_user('aluno', password='x')
        self.sala = Sala.objects.create(nome='Ginásio')
        hoje = date.today()
        self.segunda = hoje - timedelta(days=hoje.weekday()) + timedelta(days=7)
        self.fixo = HorarioFixo.objects.create(
            sala=self.sala, dia_semana=HorarioFixo.SEGUNDA, horario_inicio=time(7, 0),
            horario_fim=time(8, 30), descricao='Treino de futsal',
        )

    def pedir(self, hora, dia=None):
        self.client.force_login(self.aluno)
        return self.client.post(reverse('agendar_sala'), {
            'nome': 'Treino', 'sala': self.sala.pk, 'motivo': 'treino',
            'horario': hora.strftime('%H:%M'), 'data_inicio': (dia or self.segunda).isoformat(),
        })

    def test_pedido_em_horario_fixo_e_recusado(self):
        resp = self.pedir(time(7, 0))
        self.assertFalse(Agendamento.objects.exists())
        self.assertContains(resp, 'tem horário fixo')
        self.assertContains(resp, 'Treino de futsal')

    def test_pedido_na_faixa_de_borda_tambem_e_recusado(self):
        self.pedir(time(7, 45))
        self.assertFalse(Agendamento.objects.exists())

    def test_pedido_em_outro_dia_da_semana_e_aceito(self):
        self.pedir(time(7, 0), dia=self.segunda + timedelta(days=1))
        self.assertEqual(Agendamento.objects.count(), 1)

    def test_pedido_fora_da_janela_e_aceito(self):
        self.pedir(time(8, 50))
        self.assertEqual(Agendamento.objects.count(), 1)

    def test_aprovacao_de_pedido_anterior_ao_horario_fixo_e_barrada(self):
        pedido = Agendamento.objects.create(
            usuario=self.aluno, sala=self.sala, nome='Treino antigo', motivo='treino',
            horario=time(7, 0),
            data_inicio=timezone.make_aware(datetime.combine(self.segunda, time(7, 0))),
            status='PENDENTE',
        )
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('aprovar_reserva', args=[pedido.pk]))
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, 'PENDENTE')
        self.assertIn(
            'horário fixo', ' '.join(str(m) for m in get_messages(resp.wsgi_request))
        )

    def test_evento_sobre_horario_fixo_e_recusado(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('criar_evento'), {
            'nome': 'Torneio', 'descricao': 'Interclasse', 'categoria': 'ESPORTIVO',
            'responsavel': self.admin.pk, 'sala': self.sala.pk,
            'data_inicio': self.segunda.isoformat(), 'data_fim': self.segunda.isoformat(),
            'horario_inicio': '08:00', 'horario_fim': '09:00',
        })
        from eventos.models import Evento
        self.assertEqual(Evento.objects.count(), 0)
        self.assertContains(resp, 'horário fixo')


class PainelDeHorariosFixosTests(TestCase):
    """Cadastrar, editar e remover pelo painel, com aviso de choque."""

    def setUp(self):
        self.admin = User.objects.create_user('admin', password='x', is_staff=True)
        self.aluno = User.objects.create_user('aluno', password='x')
        self.sala = Sala.objects.create(nome='Ginásio')
        hoje = date.today()
        self.segunda = hoje - timedelta(days=hoje.weekday()) + timedelta(days=7)

    def dados(self, **extra):
        dados = {
            'sala': self.sala.pk, 'dia_semana': HorarioFixo.SEGUNDA,
            'horario_inicio': '07:00', 'horario_fim': '08:30',
            'descricao': 'Treino de futsal',
        }
        dados.update(extra)
        return dados

    def avisos(self, resp):
        return ' '.join(str(m) for m in get_messages(resp.wsgi_request))

    def test_aluno_nao_acessa_o_cadastro(self):
        self.client.force_login(self.aluno)
        self.assertIn(self.client.get(reverse('lista_horarios_fixos')).status_code, (302, 403))

    def test_admin_cadastra_informando_espaco_dia_horario_e_descricao(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('criar_horario_fixo'), self.dados())
        fixo = HorarioFixo.objects.get()
        self.assertEqual(
            (fixo.sala, fixo.dia_semana, fixo.periodo, fixo.descricao, fixo.criado_por),
            (self.sala, HorarioFixo.SEGUNDA, '07:00 às 08:30', 'Treino de futsal', self.admin),
        )

    def test_cadastro_fora_da_grade_e_recusado_com_explicacao(self):
        self.client.force_login(self.admin)
        resp = self.client.post(
            reverse('criar_horario_fixo'), self.dados(horario_inicio='19:00', horario_fim='21:00')
        )
        self.assertEqual(HorarioFixo.objects.count(), 0)
        self.assertContains(resp, 'dentro da grade')

    def test_avisa_quando_ja_ha_reserva_aprovada_no_horario(self):
        Agendamento.objects.create(
            usuario=self.aluno, sala=self.sala, nome='Treino marcado', motivo='treino',
            horario=time(7, 0),
            data_inicio=timezone.make_aware(datetime.combine(self.segunda, time(7, 0))),
            status='APROVADO',
        )
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('criar_horario_fixo'), self.dados())
        self.assertEqual(HorarioFixo.objects.count(), 1)
        aviso = self.avisos(resp)
        self.assertIn('reserva(s) aprovada(s)', aviso)
        self.assertIn(f'{self.segunda:%d/%m}', aviso)

    def test_avisa_quando_ja_ha_evento_no_horario(self):
        from eventos.models import Evento
        Evento.objects.create(
            nome='Torneio', descricao='x', categoria='ESPORTIVO', responsavel=self.admin,
            sala=self.sala, data_inicio=self.segunda, data_fim=self.segunda,
            horario_inicio=time(8, 0), horario_fim=time(9, 0),
        )
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('criar_horario_fixo'), self.dados())
        self.assertIn('Torneio', self.avisos(resp))

    def test_sem_choque_nao_avisa(self):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('criar_horario_fixo'), self.dados())
        self.assertNotIn('já havia', self.avisos(resp))

    def test_admin_edita(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('criar_horario_fixo'), self.dados())
        fixo = HorarioFixo.objects.get()
        self.client.post(
            reverse('editar_horario_fixo', args=[fixo.pk]),
            self.dados(dia_semana=2, descricao='Treino de vôlei'),
        )
        fixo.refresh_from_db()
        self.assertEqual((fixo.dia_semana, fixo.descricao), (2, 'Treino de vôlei'))

    def test_admin_remove_e_horario_volta_a_ficar_livre(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('criar_horario_fixo'), self.dados())
        fixo = HorarioFixo.objects.get()
        resp = self.client.post(reverse('remover_horario_fixo', args=[fixo.pk]))
        self.assertEqual(HorarioFixo.objects.count(), 0)
        self.assertIn('voltou a ficar livre', self.avisos(resp))

        # e o pedido naquele horário volta a ser aceito
        self.client.force_login(self.aluno)
        self.client.post(reverse('agendar_sala'), {
            'nome': 'Treino', 'sala': self.sala.pk, 'motivo': 'treino',
            'horario': '07:00', 'data_inicio': self.segunda.isoformat(),
        })
        self.assertEqual(Agendamento.objects.count(), 1)

    def test_lista_mostra_os_cadastrados(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('criar_horario_fixo'), self.dados())
        html = self.client.get(reverse('lista_horarios_fixos')).content.decode()
        self.assertIn('Treino de futsal', html)
        self.assertIn('Toda segunda-feira', html)
        self.assertIn('07:00 às 08:30', html)


class RecusaAutomaticaDeConcorrentesTests(TestCase):
    """Aprovar um pedido decide a disputa pelo horário (issue #22)."""

    def setUp(self):
        self.admin = User.objects.create_user('admin', password='x', is_staff=True)
        self.aluno = User.objects.create_user('aluno', password='x')
        self.outro = User.objects.create_user('outro', password='x')
        self.terceiro = User.objects.create_user('terceiro', password='x')
        self.sala = Sala.objects.create(nome='Quadra')
        self.outra_sala = Sala.objects.create(nome='Auditório')
        self.hora = time(7, 45)
        hoje = date.today()
        self.dia = hoje + timedelta(days=1)
        while self.dia.weekday() >= 5:
            self.dia += timedelta(days=1)

    def pedido(self, usuario, hora=None, dia=None, sala=None):
        h = hora or self.hora
        return Agendamento.objects.create(
            usuario=usuario, sala=sala or self.sala, nome=f'Treino de {usuario.username}',
            motivo='treino', horario=h,
            data_inicio=timezone.make_aware(datetime.combine(dia or self.dia, h)),
            status='PENDENTE',
        )

    def aprovar(self, agendamento, ajax=False):
        self.client.force_login(self.admin)
        extra = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'} if ajax else {}
        return self.client.post(reverse('aprovar_reserva', args=[agendamento.pk]), **extra)

    def test_aprovar_recusa_os_concorrentes_do_mesmo_horario(self):
        escolhido = self.pedido(self.aluno)
        perdedor = self.pedido(self.outro)
        outro_perdedor = self.pedido(self.terceiro)

        self.aprovar(escolhido)

        escolhido.refresh_from_db(); perdedor.refresh_from_db(); outro_perdedor.refresh_from_db()
        self.assertEqual(escolhido.status, 'APROVADO')
        self.assertEqual(perdedor.status, 'REJEITADO')
        self.assertEqual(outro_perdedor.status, 'REJEITADO')

    def test_quem_perdeu_recebe_notificacao_explicando(self):
        escolhido = self.pedido(self.aluno)
        self.pedido(self.outro)

        self.aprovar(escolhido)

        notificacao = Notificacao.objects.get(destinatario=self.outro)
        self.assertEqual(notificacao.titulo, 'Horário concedido a outro pedido')
        self.assertIn('concedido a outra solicitação', notificacao.mensagem)
        self.assertIn('Quadra', notificacao.mensagem)

    def test_pedidos_de_outro_horario_data_ou_sala_nao_sao_afetados(self):
        escolhido = self.pedido(self.aluno)
        outro_horario = self.pedido(self.outro, hora=time(8, 50))
        outro_dia = self.pedido(self.outro, dia=self.dia + timedelta(days=1))
        outra_sala = self.pedido(self.outro, sala=self.outra_sala)

        self.aprovar(escolhido)

        for pedido in (outro_horario, outro_dia, outra_sala):
            pedido.refresh_from_db()
            self.assertEqual(pedido.status, 'PENDENTE')

    def test_recusados_somem_da_fila_de_solicitacoes(self):
        escolhido = self.pedido(self.aluno)
        perdedor = self.pedido(self.outro)

        self.aprovar(escolhido)

        self.client.force_login(self.admin)
        html = self.client.get(reverse('aprovacoes')).content.decode()
        self.assertNotIn(perdedor.nome, html)

    def test_rejeitar_a_aprovada_depois_nao_reativa_os_recusados(self):
        escolhido = self.pedido(self.aluno)
        perdedor = self.pedido(self.outro)
        self.aprovar(escolhido)

        self.client.force_login(self.admin)
        self.client.post(reverse('rejeitar_reserva', args=[escolhido.pk]))

        perdedor.refresh_from_db()
        self.assertEqual(perdedor.status, 'REJEITADO')
        # e o horário volta a aceitar pedido novo
        self.client.force_login(self.terceiro)
        self.client.post(reverse('agendar_sala'), {
            'nome': 'Treino novo', 'sala': self.sala.pk, 'motivo': 'treino',
            'horario': self.hora.strftime('%H:%M'), 'data_inicio': self.dia.isoformat(),
        })
        self.assertTrue(Agendamento.objects.filter(usuario=self.terceiro, status='PENDENTE').exists())

    def test_rejeitar_um_pedido_nao_mexe_nos_outros(self):
        alvo = self.pedido(self.aluno)
        outro = self.pedido(self.outro)

        self.client.force_login(self.admin)
        self.client.post(reverse('rejeitar_reserva', args=[alvo.pk]))

        outro.refresh_from_db()
        self.assertEqual(outro.status, 'PENDENTE')

    def test_resposta_ajax_informa_quantos_foram_recusados(self):
        escolhido = self.pedido(self.aluno)
        self.pedido(self.outro)
        self.pedido(self.terceiro)

        resp = self.aprovar(escolhido, ajax=True)

        self.assertEqual(resp.json()['recusados_automaticamente'], 2)

    def test_aprovacao_sem_concorrentes_nao_recusa_nada(self):
        escolhido = self.pedido(self.aluno)
        self.aprovar(escolhido)
        self.assertEqual(Agendamento.objects.filter(status='REJEITADO').count(), 0)
