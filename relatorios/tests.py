"""Exportação das avaliações em CSV."""
import csv
from datetime import date, datetime, time, timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from avaliacoes.models import Avaliacao
from bedesk.models import Agendamento, Sala

User = get_user_model()


class ExportacaoDeAvaliacoesTests(TestCase):
    def setUp(self):
        self.aluno = User.objects.create_user('aluno', password='x', first_name='Ana', last_name='Lima')
        self.staff = User.objects.create_user('coord', password='x', is_staff=True)
        self.quadra = Sala.objects.create(nome='Ginásio')
        self.auditorio = Sala.objects.create(nome='Auditório')

    def avaliar(self, sala, nota, comentario='', hora=time(7, 0)):
        reserva = Agendamento.objects.create(
            usuario=self.aluno, sala=sala, nome='Uso', motivo='x', horario=hora,
            data_inicio=timezone.make_aware(
                datetime.combine(date.today() - timedelta(days=1), hora)
            ),
            status='APROVADO',
        )
        return Avaliacao.objects.create(
            reserva=reserva, nota=nota, limpeza=nota, estrutura=nota,
            organizacao=nota, conservacao=nota, comentario=comentario,
        )

    def baixar(self, nome_da_rota, **parametros):
        self.client.force_login(self.staff)
        resposta = self.client.get(reverse(nome_da_rota), parametros)
        self.assertEqual(resposta.status_code, 200)
        texto = resposta.content.decode('utf-8-sig')
        return resposta, list(csv.reader(StringIO(texto), delimiter=';'))

    # ---- médias ----

    def test_medias_trazem_cabecalho_e_uma_linha_por_espaco(self):
        self.avaliar(self.quadra, 5)
        _, linhas = self.baixar('exportar_medias_de_avaliacao')

        self.assertEqual(
            linhas[0],
            ['Espaço', 'Nota geral', 'Limpeza', 'Estrutura', 'Organização',
             'Conservação', 'Avaliações'],
        )
        self.assertEqual(linhas[1], ['Ginásio', '5,0', '5,0', '5,0', '5,0', '5,0', '1'])

    def test_decimal_sai_com_virgula(self):
        self.avaliar(self.quadra, 5)
        self.avaliar(self.quadra, 4, hora=time(7, 45))
        _, linhas = self.baixar('exportar_medias_de_avaliacao')
        self.assertEqual(linhas[1][1], '4,5')

    # ---- comentários ----

    def test_comentarios_trazem_espaco_data_nota_e_autor(self):
        self.avaliar(self.quadra, 2, comentario='Projetor não liga.')
        _, linhas = self.baixar('exportar_comentarios_de_avaliacao')

        self.assertEqual(linhas[0][0], 'Espaço')
        self.assertIn('Autor', linhas[0])
        self.assertIn('Comentário', linhas[0])

        linha = linhas[1]
        self.assertEqual(linha[0], 'Ginásio')
        self.assertEqual(linha[3], 'Ana Lima')
        self.assertEqual(linha[4], '2')
        self.assertEqual(linha[-1], 'Projetor não liga.')

    def test_avaliacao_sem_comentario_fica_de_fora(self):
        self.avaliar(self.quadra, 5)
        _, linhas = self.baixar('exportar_comentarios_de_avaliacao')
        self.assertEqual(len(linhas), 1, 'só o cabeçalho')

    def test_filtro_de_espaco_e_respeitado(self):
        self.avaliar(self.quadra, 2, comentario='Do ginásio')
        self.avaliar(self.auditorio, 1, comentario='Do auditório')

        _, linhas = self.baixar('exportar_comentarios_de_avaliacao', sala=self.auditorio.pk)
        self.assertEqual([l[0] for l in linhas[1:]], ['Auditório'])

    def test_filtro_invalido_nao_derruba_a_exportacao(self):
        self.avaliar(self.quadra, 2, comentario='Do ginásio')
        _, linhas = self.baixar('exportar_comentarios_de_avaliacao', sala='abc')
        self.assertEqual(len(linhas), 2)

    # ---- acentuação e acesso ----

    def test_arquivo_abre_com_acentuacao_em_planilha(self):
        self.avaliar(self.quadra, 3, comentario='Sala boa, só a organização falhou.')
        resposta, _ = self.baixar('exportar_comentarios_de_avaliacao')

        self.assertTrue(
            resposta.content.startswith('﻿'.encode('utf-8')),
            'sem o BOM, o Excel abre "Ginásio" como "GinÃ¡sio"',
        )
        self.assertIn('Ginásio'.encode('utf-8'), resposta.content)
        self.assertIn('attachment; filename=', resposta['Content-Disposition'])

    def test_aluno_nao_exporta(self):
        self.client.force_login(self.aluno)
        for rota in ('exportar_medias_de_avaliacao', 'exportar_comentarios_de_avaliacao'):
            self.assertEqual(self.client.get(reverse(rota)).status_code, 302)

    def test_visitante_nao_exporta(self):
        for rota in ('exportar_medias_de_avaliacao', 'exportar_comentarios_de_avaliacao'):
            self.assertEqual(self.client.get(reverse(rota)).status_code, 302)


class BotoesNaTelaTests(TestCase):
    """Os links de download saem da própria tela de indicadores."""

    def setUp(self):
        self.staff = User.objects.create_user('coord2', password='x', is_staff=True)
        self.sala = Sala.objects.create(nome='Ginásio')

    def test_tela_oferece_os_dois_downloads(self):
        self.client.force_login(self.staff)
        resposta = self.client.get(reverse('indicadores_avaliacoes'))
        self.assertContains(resposta, reverse('exportar_medias_de_avaliacao'))
        self.assertContains(resposta, reverse('exportar_comentarios_de_avaliacao'))

    def test_link_de_comentarios_leva_o_filtro_junto(self):
        self.client.force_login(self.staff)
        resposta = self.client.get(reverse('indicadores_avaliacoes'), {'sala': self.sala.pk})
        esperado = f"{reverse('exportar_comentarios_de_avaliacao')}?sala={self.sala.pk}"
        self.assertContains(resposta, esperado)
