from django import forms

from bedesk.models import Sala
from manutencao.models import SolicitacaoManutencao


class SolicitacaoManutencaoForm(forms.ModelForm):
    class Meta:
        model = SolicitacaoManutencao
        fields = ['sala', 'outro_local', 'categoria', 'prioridade', 'descricao', 'imagem']
        widgets = {
            'descricao': forms.Textarea(attrs={
                'rows': 5,
                'placeholder': 'Ex.: a luz do fundo da quadra está queimada e o interruptor não responde.',
            }),
            'outro_local': forms.TextInput(attrs={
                'placeholder': 'Ex.: corredor do 2º andar, banheiro masculino',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['sala'].queryset = Sala.objects.order_by('nome')
        self.fields['sala'].empty_label = 'Outro espaço (descrever abaixo)'
        self.fields['sala'].required = False

    def clean(self):
        dados = super().clean()
        if not dados.get('sala') and not (dados.get('outro_local') or '').strip():
            self.add_error('sala', 'Escolha um espaço da lista ou descreva em "Outro espaço".')
        return dados


class AtualizarStatusForm(forms.Form):
    """Usada pela administração para mover a solicitação de status."""

    status = forms.ChoiceField(
        choices=SolicitacaoManutencao.STATUS_CHOICES,
        label='Novo status',
    )
    prioridade = forms.ChoiceField(
        choices=SolicitacaoManutencao.PRIORIDADE_CHOICES,
        label='Prioridade',
    )
    observacao = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'O que foi verificado, encaminhado ou resolvido.',
        }),
        label='Observação',
    )
