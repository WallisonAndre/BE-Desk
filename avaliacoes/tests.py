"""Avaliação dos espaços: quem pode avaliar, o que fica gravado e as médias."""
from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from avaliacoes.models import Avaliacao
from avaliacoes.services import media_do_espaco, motivo_para_nao_avaliar, reservas_avaliaveis
from bedesk.models import Agendamento, Sala
from notificacoes.models import Notificacao
from eventos.models import Evento

User = get_user_model()

NOTAS_VALIDAS = {
    'nota': 4,
    'limpeza': 5,
    'estrutura': 3,
    'organizacao': 4,
    'conservacao': 4,
}


class BaseAvaliacao(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user('aluno', password='x')
        self.outro = User.objects.create_user('outro', password='x')
        self.sala = Sala.objects.create(nome='Quadra')

    def reserva(self, *, usuario=None, status='APROVADO', dias_atras=1, hora=time(7, 0)):
        dia = date.today() - timedelta(days=dias_atras)
        return Agendamento.objects.create(
            usuario=usuario or self.usuario,
            sala=self.sala,
            nome='Treino',
            motivo='treino',
            horario=hora,
            data_inicio=timezone.make_aware(datetime.combine(dia, hora)),
            status=status,
        )

    def avaliar(self, reserva, **notas):
        campos = dict(NOTAS_VALIDAS)
        campos.update(notas)
        return Avaliacao.objects.create(reserva=reserva, **campos)


class QuemPodeAvaliarTests(BaseAvaliacao):
    def test_dono_de_reserva_aprovada_ja_usada_pode_avaliar(self):
        self.assertIsNone(motivo_para_nao_avaliar(self.reserva(), self.usuario))

    def test_reserva_de_outra_pessoa_nao_pode_ser_avaliada(self):
        reserva = self.reserva(usuario=self.outro)
        self.assertEqual(motivo_para_nao_avaliar(reserva, self.usuario), 'Esta reserva não é sua.')

    def test_reserva_pendente_nao_pode_ser_avaliada(self):
        reserva = self.reserva(status='PENDENTE')
        self.assertIn('aprovadas', motivo_para_nao_avaliar(reserva, self.usuario))

    def test_reserva_rejeitada_nao_pode_ser_avaliada(self):
        reserva = self.reserva(status='REJEITADO')
        self.assertIn('aprovadas', motivo_para_nao_avaliar(reserva, self.usuario))

    def test_horario_que_ainda_nao_terminou_nao_pode_ser_avaliado(self):
        reserva = self.reserva(dias_atras=-2)  # dois dias à frente
        self.assertIn('ainda não terminou', motivo_para_nao_avaliar(reserva, self.usuario))

    def test_faixa_de_evento_nao_e_avaliavel(self):
        reserva = self.reserva()
        evento = Evento.objects.create(
            nome='Jogos',
            descricao='x',
            sala=self.sala,
            responsavel=self.usuario,
            data_inicio=date.today() - timedelta(days=1),
            data_fim=date.today() - timedelta(days=1),
            horario_inicio=time(7, 0),
            horario_fim=time(7, 45),
        )
        evento.agendamentos.add(reserva)
        self.assertIn('evento', motivo_para_nao_avaliar(reserva, self.usuario))

    def test_reserva_ja_avaliada_nao_recebe_segunda_avaliacao(self):
        reserva = self.reserva()
        self.avaliar(reserva)
        self.assertEqual(
            motivo_para_nao_avaliar(reserva, self.usuario), 'Você já avaliou esta reserva.'
        )

    def test_lista_de_avaliaveis_traz_so_o_que_falta(self):
        usada = self.reserva()
        self.reserva(dias_atras=-3)               # ainda vai acontecer
        self.reserva(status='PENDENTE')           # não aprovada
        ja_avaliada = self.reserva(hora=time(9, 35))
        self.avaliar(ja_avaliada)

        self.assertEqual([r.pk for r in reservas_avaliaveis(self.usuario)], [usada.pk])


class RegistroDaAvaliacaoTests(BaseAvaliacao):
    def test_formulario_abre_para_reserva_avaliavel(self):
        reserva = self.reserva()
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse('avaliar_reserva', args=[reserva.pk]))
        self.assertEqual(resposta.status_code, 200)

    def test_post_grava_as_cinco_notas_e_o_comentario(self):
        reserva = self.reserva()
        self.client.force_login(self.usuario)
        resposta = self.client.post(
            reverse('avaliar_reserva', args=[reserva.pk]),
            {**NOTAS_VALIDAS, 'comentario': 'Faltou papel toalha.'},
        )
        self.assertRedirects(resposta, reverse('minhas_avaliacoes'))

        avaliacao = Avaliacao.objects.get(reserva=reserva)
        self.assertEqual(avaliacao.nota, 4)
        self.assertEqual(avaliacao.limpeza, 5)
        self.assertEqual(avaliacao.estrutura, 3)
        self.assertEqual(avaliacao.comentario, 'Faltou papel toalha.')
        self.assertEqual(avaliacao.usuario, self.usuario)
        self.assertEqual(avaliacao.sala, self.sala)

    def test_comentario_e_opcional(self):
        reserva = self.reserva()
        self.client.force_login(self.usuario)
        self.client.post(reverse('avaliar_reserva', args=[reserva.pk]), NOTAS_VALIDAS)
        self.assertEqual(Avaliacao.objects.get(reserva=reserva).comentario, '')

    def test_nota_fora_de_1_a_5_nao_grava(self):
        reserva = self.reserva()
        self.client.force_login(self.usuario)
        resposta = self.client.post(
            reverse('avaliar_reserva', args=[reserva.pk]), {**NOTAS_VALIDAS, 'nota': 9}
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Avaliacao.objects.filter(reserva=reserva).exists())

    def test_avaliar_reserva_de_outro_usuario_nao_grava(self):
        reserva = self.reserva(usuario=self.outro)
        self.client.force_login(self.usuario)
        resposta = self.client.post(reverse('avaliar_reserva', args=[reserva.pk]), NOTAS_VALIDAS)
        self.assertRedirects(resposta, reverse('minhas_avaliacoes'))
        self.assertFalse(Avaliacao.objects.exists())

    def test_segundo_envio_do_mesmo_formulario_nao_duplica(self):
        reserva = self.reserva()
        self.client.force_login(self.usuario)
        self.client.post(reverse('avaliar_reserva', args=[reserva.pk]), NOTAS_VALIDAS)
        self.client.post(reverse('avaliar_reserva', args=[reserva.pk]), NOTAS_VALIDAS)
        self.assertEqual(Avaliacao.objects.filter(reserva=reserva).count(), 1)

    def test_visitante_nao_avalia(self):
        reserva = self.reserva()
        resposta = self.client.post(reverse('avaliar_reserva', args=[reserva.pk]), NOTAS_VALIDAS)
        self.assertEqual(resposta.status_code, 302)
        self.assertFalse(Avaliacao.objects.exists())


class MediasTests(BaseAvaliacao):
    def test_media_do_espaco_sai_das_notas_gerais(self):
        self.avaliar(self.reserva(hora=time(7, 0)), nota=5)
        self.avaliar(self.reserva(hora=time(7, 45)), nota=4)
        self.avaliar(self.reserva(hora=time(8, 50)), nota=3)
        self.assertEqual(media_do_espaco(self.sala), (4.0, 3))

    def test_espaco_sem_avaliacao_nao_inventa_media(self):
        self.assertEqual(media_do_espaco(self.sala), (None, 0))

    def test_media_dos_criterios_e_calculada(self):
        avaliacao = self.avaliar(
            self.reserva(), limpeza=5, estrutura=4, organizacao=4, conservacao=3
        )
        self.assertEqual(avaliacao.media_criterios, 4.0)


class IndicadoresTests(BaseAvaliacao):
    def setUp(self):
        super().setUp()
        self.staff = User.objects.create_user('coord', password='x', is_staff=True)
        self.outra_sala = Sala.objects.create(nome='Auditório')

    def test_pagina_lista_medias_melhor_e_pior(self):
        self.avaliar(self.reserva(hora=time(7, 0)), nota=5)
        ruim = Agendamento.objects.create(
            usuario=self.usuario, sala=self.outra_sala, nome='Aula', motivo='x',
            horario=time(7, 0),
            data_inicio=timezone.make_aware(
                datetime.combine(date.today() - timedelta(days=1), time(7, 0))
            ),
            status='APROVADO',
        )
        self.avaliar(ruim, nota=2)

        self.client.force_login(self.staff)
        resposta = self.client.get(reverse('indicadores_avaliacoes'))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context['melhor']['reserva__sala__nome'], 'Quadra')
        self.assertEqual(resposta.context['pior']['reserva__sala__nome'], 'Auditório')
        self.assertEqual(resposta.context['kpi_media'], 3.5)

    def test_comentarios_podem_ser_filtrados_por_espaco(self):
        self.avaliar(self.reserva(), comentario='Quadra escorregadia')
        self.client.force_login(self.staff)
        resposta = self.client.get(reverse('indicadores_avaliacoes'), {'sala': self.outra_sala.pk})
        self.assertEqual(list(resposta.context['comentarios']), [])

    def test_usuario_comum_nao_ve_os_indicadores(self):
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse('indicadores_avaliacoes'))
        self.assertEqual(resposta.status_code, 302)

    def test_dashboard_mostra_a_nota_media(self):
        self.avaliar(self.reserva(), nota=5)
        self.client.force_login(self.staff)
        resposta = self.client.get(reverse('listar_pendentes'))
        self.assertEqual(resposta.context['kpi_media_avaliacoes'], 5.0)
        self.assertEqual(resposta.context['kpi_espaco_pior'], 'Quadra')


class MinhasAvaliacoesTests(BaseAvaliacao):
    def test_lista_mostra_so_as_minhas(self):
        minha = self.avaliar(self.reserva())
        self.avaliar(self.reserva(usuario=self.outro, hora=time(9, 35)))

        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse('minhas_avaliacoes'))
        self.assertEqual([a.pk for a in resposta.context['avaliacoes']], [minha.pk])

    def test_reserva_usada_aparece_como_pendente_de_avaliacao(self):
        reserva = self.reserva()
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse('minhas_avaliacoes'))
        self.assertEqual([r.pk for r in resposta.context['pendentes']], [reserva.pk])

    def test_historico_de_reservas_oferece_o_botao_avaliar(self):
        reserva = self.reserva()
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse('lista_reserva'))
        self.assertIn(reserva.pk, resposta.context['ids_avaliaveis'])
        self.assertContains(resposta, reverse('avaliar_reserva', args=[reserva.pk]))


class MediaNasTelasDeEscolhaTests(BaseAvaliacao):
    """A nota do espaço aparece para quem está escolhendo onde reservar."""

    def espaco_avaliado(self, nome, nota):
        sala = Sala.objects.create(nome=nome)
        reserva = Agendamento.objects.create(
            usuario=self.usuario, sala=sala, nome='Uso', motivo='x', horario=time(7, 0),
            data_inicio=timezone.make_aware(
                datetime.combine(date.today() - timedelta(days=1), time(7, 0))
            ),
            status='APROVADO',
        )
        self.avaliar(reserva, nota=nota)
        return sala

    def test_card_do_local_mostra_a_media_e_a_quantidade(self):
        self.avaliar(self.reserva(hora=time(7, 0)), nota=5)
        self.avaliar(self.reserva(hora=time(7, 45)), nota=4)

        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse('lista_locais'))

        local = next(l for l in resposta.context['locais'] if l.pk == self.sala.pk)
        self.assertEqual(local.media_avaliacao, 4.5)
        self.assertEqual(local.total_avaliacoes, 2)
        self.assertContains(resposta, '4,5')

    def test_espaco_sem_avaliacao_aparece_como_sem_avaliacoes(self):
        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse('lista_locais'))

        local = next(l for l in resposta.context['locais'] if l.pk == self.sala.pk)
        self.assertIsNone(local.media_avaliacao)
        self.assertEqual(local.total_avaliacoes, 0)
        self.assertContains(resposta, 'sem avaliações')

    def test_pagina_da_sala_mostra_a_media(self):
        self.avaliar(self.reserva(), nota=3)
        resposta = self.client.get(reverse('detalhe_sala', args=[self.sala.nome]))
        self.assertEqual(resposta.context['media_avaliacao'], 3.0)
        self.assertEqual(resposta.context['total_avaliacoes'], 1)

    def test_pagina_da_sala_sem_avaliacao_nao_inventa_nota(self):
        resposta = self.client.get(reverse('detalhe_sala', args=[self.sala.nome]))
        self.assertIsNone(resposta.context['media_avaliacao'])
        self.assertContains(resposta, 'Nenhuma avaliação ainda')

    def test_listagem_nao_faz_uma_consulta_por_espaco(self):
        """Mais espaços não podem significar mais consultas."""
        self.client.force_login(self.usuario)
        self.espaco_avaliado('Auditório', 4)

        with CaptureQueriesContext(connection) as com_dois:
            self.client.get(reverse('lista_locais'))

        for indice, nome in enumerate(['Quadra', 'Laboratório', 'Sala de Reuniões']):
            self.espaco_avaliado(nome, 3 + indice % 2)

        with CaptureQueriesContext(connection) as com_cinco:
            self.client.get(reverse('lista_locais'))

        self.assertEqual(len(com_cinco), len(com_dois))


class AvisoDeAvaliacaoBaixaTests(BaseAvaliacao):
    """Nota ruim avisa o staff na hora, em vez de esperar alguém abrir o painel."""

    def setUp(self):
        super().setUp()
        self.staff = User.objects.create_user('coord', password='x', is_staff=True)
        self.outro_staff = User.objects.create_user('direcao', password='x', is_staff=True)
        self.inativo = User.objects.create_user(
            'antigo', password='x', is_staff=True, is_active=False
        )

    def avisos(self, destinatario=None):
        avisos = Notificacao.objects.filter(tipo='AVALIACAO_BAIXA')
        return avisos.filter(destinatario=destinatario) if destinatario else avisos

    def enviar(self, nota, comentario=''):
        reserva = self.reserva()
        self.client.force_login(self.usuario)
        return self.client.post(
            reverse('avaliar_reserva', args=[reserva.pk]),
            {**NOTAS_VALIDAS, 'nota': nota, 'comentario': comentario},
        )

    def test_nota_1_avisa_todo_staff_ativo(self):
        self.enviar(1)
        self.assertEqual(self.avisos().count(), 2)
        self.assertTrue(self.avisos(self.staff).exists())
        self.assertTrue(self.avisos(self.outro_staff).exists())

    def test_nota_2_tambem_avisa(self):
        self.enviar(2)
        self.assertEqual(self.avisos().count(), 2)

    def test_nota_3_nao_avisa(self):
        self.enviar(3)
        self.assertFalse(self.avisos().exists())

    def test_nota_5_nao_avisa(self):
        self.enviar(5)
        self.assertFalse(self.avisos().exists())

    def test_staff_inativo_nao_recebe(self):
        self.enviar(1)
        self.assertFalse(self.avisos(self.inativo).exists())

    def test_quem_avaliou_nao_recebe_o_aviso(self):
        self.enviar(1)
        self.assertFalse(self.avisos(self.usuario).exists())

    def test_mensagem_traz_espaco_e_nota(self):
        self.enviar(2)
        aviso = self.avisos(self.staff).first()
        self.assertEqual(aviso.titulo, 'Avaliação baixa em Quadra')
        self.assertIn('Quadra', aviso.mensagem)
        self.assertIn('nota 2 de 5', aviso.mensagem)

    def test_comentario_entra_na_mensagem(self):
        self.enviar(1, comentario='Duas luminárias queimadas.')
        self.assertIn('Duas luminárias queimadas.', self.avisos(self.staff).first().mensagem)

    def test_sem_comentario_a_mensagem_nao_fica_truncada(self):
        self.enviar(1)
        mensagem = self.avisos(self.staff).first().mensagem
        self.assertNotIn('Comentário', mensagem)
        self.assertTrue(mensagem.endswith('de 5.'))

    def test_aviso_leva_para_os_indicadores(self):
        self.enviar(1)
        self.assertEqual(self.avisos(self.staff).first().link, '/painel-admin/avaliacoes/')

    def test_avaliacao_que_nao_grava_nao_avisa(self):
        """Formulário inválido não pode gerar aviso de nota baixa."""
        reserva = self.reserva()
        self.client.force_login(self.usuario)
        self.client.post(
            reverse('avaliar_reserva', args=[reserva.pk]),
            {**NOTAS_VALIDAS, 'nota': 1, 'limpeza': 99},
        )
        self.assertFalse(Avaliacao.objects.filter(reserva=reserva).exists())
        self.assertFalse(self.avisos().exists())
