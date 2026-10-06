"""Contrato entre o modelo de notificação e o sino do menu.

O sino monta a lista com o ícone e a cor que a API manda. Quando ele tinha a
própria tabela de tipos, um tipo novo (`AVALIACAO_BAIXA`) não existia nela e a
lista inteira morria em "Carregando...". Estes testes guardam o contrato.
"""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from notificacoes.models import Notificacao

User = get_user_model()


class ContratoDoSinoTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user('aluno', password='x')

    def test_todo_tipo_declarado_tem_icone_e_cor(self):
        """Tipo novo sem entrada cai no padrão calado — que isso apareça aqui."""
        declarados = {tipo for tipo, _rotulo in Notificacao.TIPO_CHOICES}
        self.assertEqual(declarados - set(Notificacao.ICONES), set(), 'tipos sem ícone')
        self.assertEqual(declarados - set(Notificacao.CORES), set(), 'tipos sem cor')
        self.assertEqual(set(Notificacao.ICONES) - declarados, set(), 'ícone de tipo inexistente')

    def test_api_manda_icone_e_cor_de_cada_notificacao(self):
        for tipo, _rotulo in Notificacao.TIPO_CHOICES:
            Notificacao.objects.create(
                destinatario=self.usuario, titulo=f'titulo {tipo}', mensagem='m', tipo=tipo
            )

        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse('notificacoes_api'))
        self.assertEqual(resposta.status_code, 200)

        itens = json.loads(resposta.content)['notifications']
        self.assertEqual(len(itens), len(Notificacao.TIPO_CHOICES))
        for item in itens:
            self.assertTrue(item['icone'], f"{item['tipo']} veio sem ícone")
            self.assertTrue(item['cor'], f"{item['tipo']} veio sem cor")

    def test_mensagem_com_html_chega_intacta_para_a_tela_escapar(self):
        """O comentário de uma avaliação é texto de usuário e entra na mensagem."""
        texto = 'Projetor <script>alert(1)</script> não liga'
        Notificacao.objects.create(
            destinatario=self.usuario, titulo='Avaliação baixa', mensagem=texto,
            tipo='AVALIACAO_BAIXA',
        )

        self.client.force_login(self.usuario)
        resposta = self.client.get(reverse('notificacoes_api'))
        item = json.loads(resposta.content)['notifications'][0]
        self.assertEqual(item['mensagem'], texto)
