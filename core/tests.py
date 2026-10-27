from django.test import TestCase
from django.urls import reverse


class HomeInstitucionalTests(TestCase):
    def test_home_apresenta_identidade_institucional_e_fluxo_sem_propaganda(self):
        resposta = self.client.get(reverse('inicio'))
        self.assertEqual(resposta.status_code, 200)

        conteudo = resposta.content.decode('utf-8')
        # Identificação institucional no cabeçalho, corpo e rodapé
        self.assertIn('IFRN', conteudo)
        self.assertIn('São Paulo do Potengi', conteudo)
        self.assertIn('Bloco E', conteudo)

        # O que é, quem usa, como acessa e o que dá para fazer
        self.assertIn('SUAP', conteudo)
        self.assertIn('alunos', conteudo.lower())
        self.assertIn('servidores', conteudo.lower())
        self.assertIn('Locais', conteudo)
        self.assertIn('Reservas', conteudo)
        self.assertIn('Eventos', conteudo)

        # Seção de dúvidas frequentes permanece
        self.assertIn('id="faq"', conteudo)
        self.assertIn('frequentes', conteudo)

        # Sem promessas de propaganda
        self.assertNotIn('sem atrito', conteudo.lower())
        self.assertNotIn('aprovação instantânea', conteudo.lower())
