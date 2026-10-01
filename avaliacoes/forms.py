"""Formulário de avaliação de um espaço."""

from django import forms

from avaliacoes.models import Avaliacao


class AvaliacaoForm(forms.ModelForm):
    """Nota geral, os quatro critérios e um comentário opcional.

    As notas saem como botões de rádio porque a tela os desenha como
    estrelas; o comentário é o único campo que pode ficar em branco.
    """

    class Meta:
        model = Avaliacao
        fields = ['nota', 'limpeza', 'estrutura', 'organizacao', 'conservacao', 'comentario']
        widgets = {
            'nota': forms.RadioSelect(),
            'limpeza': forms.RadioSelect(),
            'estrutura': forms.RadioSelect(),
            'organizacao': forms.RadioSelect(),
            'conservacao': forms.RadioSelect(),
            'comentario': forms.Textarea(
                attrs={
                    'rows': 4,
                    'placeholder': 'Ex.: a quadra estava limpa, mas duas luminárias não acendem.',
                }
            ),
        }

    @property
    def campos_criterio(self):
        """Os quatro critérios, para a tela agrupá-los separados da nota geral."""
        return [self[nome] for nome in Avaliacao.CRITERIOS]
