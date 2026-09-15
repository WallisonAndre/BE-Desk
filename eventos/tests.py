"""Conflitos de horário entre eventos e reservas (issue #7)."""
import importlib
from datetime import date, datetime, timedelta
from unittest import mock

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bedesk.models import Agendamento, Sala
from eventos.forms import EventoForm
from eventos.models import Evento
from eventos.services import slots_ocupados
from reservas.forms import AgendarForm

User = get_user_model()


def _hora(texto):
    return datetime.strptime(texto, '%H:%M').time()


def _proximo_dia_util():
    dia = date.today() + timedelta(days=1)
    while dia.weekday() >= 5:
        dia += timedelta(days=1)
    return dia


class ConflitosBase(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', password='x', is_staff=True, is_superuser=True)
        self.aluno = User.objects.create_user('aluno', password='x')
        self.outro_aluno = User.objects.create_user('outro', password='x')
        self.sala = Sala.objects.create(nome='Quadra')
        self.dia = _proximo_dia_util()

    def dados_evento(self, **extra):
        dados = {
            'nome': 'Torneio', 'descricao': 'Interclasse', 'categoria': 'ESPORTIVO',
            'responsavel': self.admin.pk, 'sala': self.sala.pk,
            'data_inicio': self.dia.isoformat(), 'data_fim': self.dia.isoformat(),
            'horario_inicio': '14:00', 'horario_fim': '16:00',
        }
        dados.update(extra)
        return dados

    def criar_evento(self, **extra):
        self.client.force_login(self.admin)
        return self.client.post(reverse('criar_evento'), self.dados_evento(**extra))

    def faixas_do_evento(self, evento):
        return sorted(a.horario.strftime('%H:%M') for a in evento.agendamentos.all())

    def agendamento(self, hora, status='APROVADO', usuario=None):
        h = _hora(hora)
        return Agendamento.objects.create(
            usuario=usuario or self.aluno, sala=self.sala, nome='Treino', motivo='treino', horario=h,
            data_inicio=timezone.make_aware(datetime.combine(self.dia, h)), status=status,
        )

    def pedir_reserva(self, hora, usuario=None):
        self.client.force_login(usuario or self.aluno)
        return self.client.post(reverse('agendar_sala'), {
            'nome': 'Treino', 'sala': self.sala.pk, 'motivo': 'treino',
            'horario': hora, 'data_inicio': self.dia.isoformat(),
        })

    def aprovar(self, agendamento, ajax=False):
        self.client.force_login(self.admin)
        extra = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'} if ajax else {}
        return self.client.post(reverse('aprovar_reserva', args=[agendamento.pk]), **extra)

    def ocupacoes_aprovadas(self, hora):
        return Agendamento.objects.filter(
            sala=self.sala, data_inicio__date=self.dia, horario=_hora(hora), status='APROVADO',
        ).count()


class OcupacaoDaGradeTests(ConflitosBase):
    def ocupacao(self, inicio, fim):
        evento = Evento(sala=self.sala, data_inicio=self.dia, data_fim=self.dia,
                        horario_inicio=_hora(inicio), horario_fim=_hora(fim))
        return [hora.strftime('%H:%M') for _, hora in slots_ocupados(evento)]

    def test_evento_ocupa_toda_faixa_que_se_sobrepoe(self):
        self.assertEqual(self.ocupacao('14:00', '16:00'), ['13:45', '14:50', '15:35'])

    def test_evento_curto_entre_dois_inicios_ocupa_a_faixa(self):
        self.assertEqual(self.ocupacao('14:00', '14:40'), ['13:45'])

    def test_evento_que_termina_no_fim_da_faixa_nao_ocupa_a_seguinte(self):
        self.assertEqual(self.ocupacao('14:00', '14:30'), ['13:45'])

    def test_criar_evento_reserva_as_faixas_na_grade(self):
        self.criar_evento()
        self.assertEqual(self.faixas_do_evento(Evento.objects.get()), ['13:45', '14:50', '15:35'])


class EventoContraEventoTests(ConflitosBase):
    def test_eventos_colados_sao_aceitos(self):
        self.criar_evento(horario_inicio='08:00', horario_fim='10:00')
        self.criar_evento(nome='Palestra', horario_inicio='10:00', horario_fim='12:00')
        self.assertEqual(Evento.objects.count(), 2)

    def test_eventos_sobrepostos_sao_recusados(self):
        self.criar_evento(horario_inicio='08:00', horario_fim='10:00')
        resp = self.criar_evento(nome='Palestra', horario_inicio='09:00', horario_fim='11:00')
        self.assertEqual(Evento.objects.count(), 1)
        self.assertContains(resp, 'pelo evento &quot;Torneio&quot;')

    def test_eventos_sobrepostos_fora_da_grade_sao_recusados(self):
        self.criar_evento(horario_inicio='18:30', horario_fim='20:00')
        self.criar_evento(nome='Palestra', horario_inicio='19:00', horario_fim='21:00')
        self.assertEqual(Evento.objects.count(), 1)

    def test_eventos_colados_fora_da_grade_sao_aceitos(self):
        self.criar_evento(horario_inicio='18:30', horario_fim='19:30')
        self.criar_evento(nome='Palestra', horario_inicio='19:30', horario_fim='21:00')
        self.assertEqual(Evento.objects.count(), 2)

    def test_evento_de_varios_dias_colide_com_evento_no_meio(self):
        fim = self.dia + timedelta(days=2)
        self.criar_evento(data_fim=fim.isoformat(), horario_inicio='08:00', horario_fim='10:00')
        meio = (self.dia + timedelta(days=1)).isoformat()
        self.criar_evento(nome='Palestra', data_inicio=meio, data_fim=meio,
                          horario_inicio='09:00', horario_fim='09:30')
        self.assertEqual(Evento.objects.count(), 1)

    def test_evento_cancelado_nao_bloqueia(self):
        self.criar_evento()
        self.client.post(reverse('cancelar_evento', args=[Evento.objects.get().pk]))
        self.criar_evento(nome='Palestra')
        self.assertEqual(Evento.objects.filter(status=Evento.PROGRAMADO).count(), 1)

    def test_editar_evento_nao_conflita_consigo_mesmo(self):
        self.criar_evento()
        evento = Evento.objects.get()
        self.client.post(reverse('editar_evento', args=[evento.pk]), self.dados_evento(descricao='Nova descrição'))
        evento.refresh_from_db()
        self.assertEqual(evento.descricao, 'Nova descrição')
        self.assertEqual(self.faixas_do_evento(evento), ['13:45', '14:50', '15:35'])


class EventoContraReservaTests(ConflitosBase):
    def test_evento_recusado_por_reserva_aprovada_na_faixa_de_borda(self):
        self.agendamento('13:45')
        resp = self.criar_evento()
        self.assertEqual(Evento.objects.count(), 0)
        self.assertContains(resp, 'pela reserva &quot;Treino&quot;')

    def test_reserva_na_faixa_do_evento_e_recusada(self):
        self.criar_evento()
        self.pedir_reserva('13:45')
        self.assertFalse(Agendamento.objects.filter(status='PENDENTE').exists())

    def test_reserva_fora_da_grade_e_recusada(self):
        self.pedir_reserva('14:10')
        self.assertFalse(Agendamento.objects.exists())

    def test_reserva_depois_de_evento_na_fronteira_segue_livre(self):
        self.criar_evento(horario_inicio='14:00', horario_fim='14:30')
        self.pedir_reserva('14:50')
        self.assertTrue(Agendamento.objects.filter(status='PENDENTE', horario=_hora('14:50')).exists())

    def test_pedido_pendente_sob_evento_nao_pode_ser_aprovado(self):
        pedido = self.agendamento('14:50', status='PENDENTE')
        self.criar_evento()
        self.assertEqual(Evento.objects.count(), 1)
        resp = self.aprovar(pedido)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, 'PENDENTE')
        self.assertEqual(self.ocupacoes_aprovadas('14:50'), 1)
        self.assertIn('Torneio', ' '.join(str(m) for m in get_messages(resp.wsgi_request)))

    def test_aprovacao_por_ajax_recusada_com_409(self):
        pedido = self.agendamento('14:50', status='PENDENTE')
        self.criar_evento()
        resp = self.aprovar(pedido, ajax=True)
        self.assertEqual(resp.status_code, 409)
        self.assertFalse(resp.json()['success'])

    def test_aprovacao_sem_conflito_continua_funcionando(self):
        pedido = self.agendamento('09:35', status='PENDENTE')
        self.aprovar(pedido)
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, 'APROVADO')


class ProtecaoDasFaixasDoEventoTests(ConflitosBase):
    def setUp(self):
        super().setUp()
        self.criar_evento(responsavel=self.aluno.pk)
        self.faixa = Evento.objects.get().agendamentos.get(horario=_hora('14:50'))

    def test_responsavel_nao_cancela_faixa_do_evento(self):
        self.client.force_login(self.aluno)
        self.client.post(reverse('cancelar_reserva_usuario', args=[self.faixa.pk]))
        self.faixa.refresh_from_db()
        self.assertEqual(self.faixa.status, 'APROVADO')

    def test_faixas_do_evento_nao_aparecem_em_minhas_reservas(self):
        self.client.force_login(self.aluno)
        resp = self.client.get(reverse('lista_reserva'))
        self.assertEqual(resp.context['kpi_proximas'], 0)
        self.assertNotIn(self.faixa, list(resp.context['reservas_ativas']))

    def test_faixa_do_evento_nao_pode_ser_rejeitada_pela_url(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('rejeitar_reserva', args=[self.faixa.pk]))
        self.faixa.refresh_from_db()
        self.assertEqual(self.faixa.status, 'APROVADO')

    def test_cenario_do_cancelamento_nao_duplica_ocupacao(self):
        self.client.force_login(self.aluno)
        self.client.post(reverse('cancelar_reserva_usuario', args=[self.faixa.pk]))
        self.pedir_reserva('14:50', usuario=self.outro_aluno)
        self.assertEqual(self.ocupacoes_aprovadas('14:50'), 1)
        self.assertFalse(Agendamento.objects.filter(usuario=self.outro_aluno).exists())


class ChecagemNaGravacaoTests(ConflitosBase):
    """Simula outra requisição gravando entre a validação do formulário e a gravação."""

    def test_evento_e_conferido_de_novo_ao_gravar(self):
        original = EventoForm.is_valid

        def valida_e_outra_requisicao_ocupa(form):
            valido = original(form)
            self.agendamento('14:50')
            return valido

        with mock.patch.object(EventoForm, 'is_valid', valida_e_outra_requisicao_ocupa):
            resp = self.criar_evento()
        self.assertEqual(Evento.objects.count(), 0)
        self.assertContains(resp, 'já está ocupado')

    def test_reserva_e_conferida_de_novo_ao_gravar(self):
        """Só aprovação ocupa: a reconferência barra quando surge uma aprovada."""
        original = AgendarForm.is_valid

        def valida_e_outra_requisicao_aprova(form):
            valido = original(form)
            self.agendamento('09:35', status='APROVADO', usuario=self.outro_aluno)
            return valido

        with mock.patch.object(AgendarForm, 'is_valid', valida_e_outra_requisicao_aprova):
            self.pedir_reserva('09:35')
        self.assertFalse(Agendamento.objects.filter(usuario=self.aluno).exists())

    def test_pedido_pendente_de_outra_pessoa_nao_impede_a_gravacao(self):
        """Vários alunos podem pedir o mesmo horário enquanto ninguém aprovou."""
        original = AgendarForm.is_valid

        def valida_e_outra_requisicao_pede(form):
            valido = original(form)
            self.agendamento('09:35', status='PENDENTE', usuario=self.outro_aluno)
            return valido

        with mock.patch.object(AgendarForm, 'is_valid', valida_e_outra_requisicao_pede):
            self.pedir_reserva('09:35')
        self.assertTrue(Agendamento.objects.filter(usuario=self.aluno, status='PENDENTE').exists())

    def test_aprovacao_trava_a_sala(self):
        pedido = self.agendamento('09:35', status='PENDENTE')
        with mock.patch('core.views.dashboard.travar_sala') as trava:
            self.aprovar(pedido)
        trava.assert_called_once_with(self.sala.pk)

    def test_criacao_de_evento_trava_a_sala(self):
        with mock.patch('eventos.views.eventos.travar_sala') as trava:
            self.criar_evento()
        trava.assert_called_once_with(self.sala.pk)


class MigracaoDeEventosAntigosTests(ConflitosBase):
    def setUp(self):
        super().setUp()
        self.migracao = importlib.import_module('eventos.migrations.0003_ocupacao_por_sobreposicao')

    def evento_da_regra_antiga(self):
        """Evento criado antes da mudança: sem a faixa de borda das 13:45."""
        self.criar_evento()
        evento = Evento.objects.get()
        evento.agendamentos.filter(horario=_hora('13:45')).delete()
        return evento

    def test_completa_a_faixa_de_borda(self):
        evento = self.evento_da_regra_antiga()
        self.assertEqual(self.faixas_do_evento(evento), ['14:50', '15:35'])
        self.migracao.completar_ocupacao(django_apps, None)
        self.assertEqual(self.faixas_do_evento(evento), ['13:45', '14:50', '15:35'])

    def test_nao_ocupa_faixa_que_ja_tem_reserva_aprovada(self):
        evento = self.evento_da_regra_antiga()
        reserva = self.agendamento('13:45')
        with mock.patch('builtins.print'):
            self.migracao.completar_ocupacao(django_apps, None)
        self.assertEqual(self.faixas_do_evento(evento), ['14:50', '15:35'])
        self.assertEqual(self.ocupacoes_aprovadas('13:45'), 1)
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, 'APROVADO')

    def test_ignora_evento_cancelado(self):
        evento = self.evento_da_regra_antiga()
        Evento.objects.filter(pk=evento.pk).update(status=Evento.CANCELADO)
        self.migracao.completar_ocupacao(django_apps, None)
        self.assertEqual(self.faixas_do_evento(evento), ['14:50', '15:35'])

    def test_rodar_duas_vezes_nao_duplica(self):
        evento = self.evento_da_regra_antiga()
        self.migracao.completar_ocupacao(django_apps, None)
        self.migracao.completar_ocupacao(django_apps, None)
        self.assertEqual(self.faixas_do_evento(evento), ['13:45', '14:50', '15:35'])
