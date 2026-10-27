from pathlib import Path

from django.conf import settings
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


class CssArquiteturaTests(TestCase):
    def test_templates_nao_possuem_blocos_style_embutidos(self):
        templates_dir = Path(settings.BASE_DIR) / 'templates'
        arquivos_com_style = []
        for arquivo in templates_dir.rglob('*.html'):
            texto = arquivo.read_text(encoding='utf-8')
            if '<style' in texto:
                arquivos_com_style.append(str(arquivo.relative_to(settings.BASE_DIR)))
        self.assertEqual(arquivos_com_style, [])

    def test_folhas_mortas_foram_removidas_e_folhas_por_tela_existem(self):
        css_dir = Path(settings.BASE_DIR) / 'static' / 'css'
        self.assertFalse((css_dir / 'estilo.css').exists())
        self.assertFalse((css_dir / 'salas.css').exists())

        for folha in ('bedesk-theme.css', 'base.css', 'inicio.css', 'locais.css', 'grade.css', 'notificacoes.css'):
            self.assertTrue((css_dir / folha).exists(), f'Folha {folha} deve existir em static/css/')

        tema = (css_dir / 'bedesk-theme.css').read_text(encoding='utf-8')
        self.assertIn('--brand-lime:', tema)
        self.assertIn('--brand-ifrn-red:', tema)
        self.assertIn('[data-theme="light"]', tema)

