"""Avaliação dos espaços: quem pode avaliar, o que fica gravado e as médias."""
from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from avaliacoes.models import Avaliacao
from avaliacoes.services import (
    MINIMO_PARA_RANKING,
    espacos_no_ranking,
    mapa_de_medias,
    media_do_espaco,
    medias_por_espaco,
    melhor_e_pior,
    motivo_para_nao_avaliar,
    reservas_avaliaveis,
)
from bedesk.models import Agendamento, Sala
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

    def avaliacoes_para(self, sala, notas, usuario=None):
        """Uma reserva usada e avaliada por nota informada, em horários distintos."""
        horarios = [time(7, 0), time(7, 45), time(8, 50), time(9, 35), time(10, 30), time(11, 15)]
        criadas = []
        for indice, nota in enumerate(notas):
            hora = horarios[indice % len(horarios)]
            dia = date.today() - timedelta(days=1 + indice // len(horarios))
            reserva = Agendamento.objects.create(
                usuario=usuario or self.usuario, sala=sala, nome='Uso', motivo='x',
                horario=hora,
                data_inicio=timezone.make_aware(datetime.combine(dia, hora)),
                status='APROVADO',
            )
            criadas.append(self.avaliar(reserva, nota=nota))
        return criadas


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
        self.avaliacoes_para(self.sala, [5, 5, 5])
        self.avaliacoes_para(self.outra_sala, [2, 2, 2])

        self.client.force_login(self.staff)
        resposta = self.client.get(reverse('indicadores_avaliacoes'))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context['melhor']['nome'], 'Quadra')
        self.assertEqual(resposta.context['pior']['nome'], 'Auditório')
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

    def test_dashboard_mostra_a_nota_media_e_o_pior_espaco(self):
        self.avaliacoes_para(self.sala, [5, 5, 5])
        self.avaliacoes_para(self.outra_sala, [2, 2, 2])

        self.client.force_login(self.staff)
        resposta = self.client.get(reverse('listar_pendentes'))
        self.assertEqual(resposta.context['kpi_media_avaliacoes'], 3.5)
        self.assertEqual(resposta.context['kpi_espaco_pior'], 'Auditório')


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


class RankingComMinimoTests(BaseAvaliacao):
    """Melhor e pior só entre espaços com avaliações suficientes."""

    def setUp(self):
        super().setUp()
        self.staff = User.objects.create_user('coord2', password='x', is_staff=True)
        self.recem_avaliado = Sala.objects.create(nome='Auditório')
        self.nunca_avaliado = Sala.objects.create(nome='Sala de Reuniões')

    def test_espaco_com_uma_nota_baixa_nao_vira_o_pior(self):
        self.avaliacoes_para(self.sala, [4, 4, 4])
        self.avaliacoes_para(self.recem_avaliado, [1])

        melhor, pior = melhor_e_pior()
        self.assertEqual(melhor['nome'], 'Quadra')
        self.assertIsNone(pior, 'com um elegível só, não há pior a apontar')

    def test_pior_aparece_quando_o_espaco_atinge_o_minimo(self):
        self.avaliacoes_para(self.sala, [4, 4, 4])
        self.avaliacoes_para(self.recem_avaliado, [1, 1, 1])

        melhor, pior = melhor_e_pior()
        self.assertEqual(melhor['nome'], 'Quadra')
        self.assertEqual(pior['nome'], 'Auditório')

    def test_minimo_fica_em_um_lugar_so(self):
        self.avaliacoes_para(self.sala, [3] * (MINIMO_PARA_RANKING - 1))
        self.assertEqual(espacos_no_ranking(), [])

        self.avaliacoes_para(self.sala, [3], usuario=self.outro)
        self.assertEqual([l['nome'] for l in espacos_no_ranking()], ['Quadra'])

    def test_espaco_abaixo_do_minimo_continua_na_tabela_marcado(self):
        self.avaliacoes_para(self.recem_avaliado, [2])

        linha = next(l for l in medias_por_espaco() if l['nome'] == 'Auditório')
        self.assertEqual(linha['media'], 2.0)
        self.assertEqual(linha['total'], 1)
        self.assertFalse(linha['no_ranking'])

        self.client.force_login(self.staff)
        resposta = self.client.get(reverse('indicadores_avaliacoes'))
        self.assertContains(resposta, 'Auditório')
        self.assertContains(resposta, 'poucas avaliações')

    def test_espaco_sem_avaliacao_aparece_como_sem_avaliacoes(self):
        linha = next(l for l in medias_por_espaco() if l['nome'] == 'Sala de Reuniões')
        self.assertIsNone(linha['media'])
        self.assertEqual(linha['total'], 0)

        self.client.force_login(self.staff)
        resposta = self.client.get(reverse('indicadores_avaliacoes'))
        self.assertContains(resposta, 'Sala de Reuniões')
        self.assertContains(resposta, 'sem avaliações')

    def test_espaco_sem_avaliacao_vai_para_o_fim_da_lista(self):
        self.avaliacoes_para(self.sala, [3, 3, 3])
        nomes = [l['nome'] for l in medias_por_espaco()]
        self.assertEqual(nomes[-1], 'Sala de Reuniões')

    def test_media_nao_e_inflada_por_reserva_sem_avaliacao(self):
        """A reserva não avaliada entra na junção e não pode mexer na média."""
        self.avaliacoes_para(self.sala, [2, 4, 3])
        self.reserva(hora=time(16, 30))  # usada, nunca avaliada

        linha = next(l for l in medias_por_espaco() if l['nome'] == 'Quadra')
        self.assertEqual(linha['media'], 3.0)
        self.assertEqual(linha['total'], 3)

    def test_dashboard_nao_aponta_pior_abaixo_do_minimo(self):
        self.avaliacoes_para(self.recem_avaliado, [1, 1])

        self.client.force_login(self.staff)
        resposta = self.client.get(reverse('listar_pendentes'))
        self.assertEqual(resposta.context['kpi_espaco_pior'], '—')

    def test_grafico_do_dashboard_ignora_espaco_sem_avaliacao(self):
        self.avaliacoes_para(self.sala, [5, 5, 5])

        self.client.force_login(self.staff)
        resposta = self.client.get(reverse('listar_pendentes'))
        self.assertIn('Quadra', resposta.context['aval_labels'])
        self.assertNotIn('Sala de Reuniões', resposta.context['aval_labels'])

    def test_pagina_avisa_quando_ninguem_atinge_o_minimo(self):
        self.avaliacoes_para(self.sala, [5])

        self.client.force_login(self.staff)
        resposta = self.client.get(reverse('indicadores_avaliacoes'))
        self.assertIsNone(resposta.context['melhor'])
        self.assertContains(resposta, 'Ainda não dá para apontar o melhor e o pior')

    def test_mapa_de_medias_continua_servindo_os_cards(self):
        self.avaliacoes_para(self.sala, [4, 5])
        mapa = mapa_de_medias()
        self.assertEqual(mapa[self.sala.pk], (4.5, 2))
        self.assertEqual(mapa[self.nunca_avaliado.pk], (None, 0))


class TextoDeQuantidadeTests(BaseAvaliacao):
    """O plural de 'avaliação' já saiu errado uma vez ('avaliaçãoões')."""

    def setUp(self):
        super().setUp()
        self.staff = User.objects.create_user('coord3', password='x', is_staff=True)

    def test_singular_na_pagina_do_espaco(self):
        self.avaliacoes_para(self.sala, [4])
        resposta = self.client.get(reverse('detalhe_sala', args=[self.sala.nome]))
        self.assertContains(resposta, '1 avaliação de quem já usou')

    def test_plural_na_pagina_do_espaco(self):
        self.avaliacoes_para(self.sala, [4, 5])
        resposta = self.client.get(reverse('detalhe_sala', args=[self.sala.nome]))
        self.assertContains(resposta, '2 avaliações de quem já usou')

    def test_plural_no_dashboard(self):
        self.avaliacoes_para(self.sala, [4, 5, 3])
        self.client.force_login(self.staff)
        resposta = self.client.get(reverse('listar_pendentes'))
        self.assertContains(resposta, '3 avaliações')
        self.assertNotContains(resposta, 'avaliaçãoões')
