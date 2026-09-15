from datetime import datetime

from django import forms
from django.contrib.auth import get_user_model

from bedesk.models import Sala
from eventos.models import Evento
from eventos.services import buscar_conflitos

User = get_user_model()


def mensagem_de_conflito(sala, conflitos):
    """Aviso de conflito, usado no formulário e na checagem repetida ao gravar."""
    detalhes = '; '.join(conflitos[:5])
    extra = f'; e mais {len(conflitos) - 5}' if len(conflitos) > 5 else ''
    return f'O espaço {sala.nome} já está ocupado {detalhes}{extra}. Ajuste a data ou o horário.'


class EventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        fields = [
            'nome', 'descricao', 'categoria', 'responsavel', 'sala',
            'data_inicio', 'data_fim', 'horario_inicio', 'horario_fim',
        ]
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 4}),
            'data_inicio': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'data_fim': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'horario_inicio': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'horario_fim': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'nome': forms.TextInput(attrs={'placeholder': 'Ex.: Torneio de futsal interclasses'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['sala'].queryset = Sala.objects.order_by('nome')
        self.fields['responsavel'].queryset = User.objects.filter(is_active=True).order_by('username')
        for campo in ('data_inicio', 'data_fim'):
            self.fields[campo].input_formats = ['%Y-%m-%d']
        for campo in ('horario_inicio', 'horario_fim'):
            self.fields[campo].input_formats = ['%H:%M', '%H:%M:%S']

    def clean(self):
        dados = super().clean()
        data_inicio = dados.get('data_inicio')
        data_fim = dados.get('data_fim')
        hora_inicio = dados.get('horario_inicio')
        hora_fim = dados.get('horario_fim')

        if data_inicio and data_fim and data_fim < data_inicio:
            self.add_error('data_fim', 'A data de término não pode ser anterior à de início.')
            return dados

        if hora_inicio and hora_fim and hora_fim <= hora_inicio:
            self.add_error('horario_fim', 'O horário de término deve ser depois do de início.')
            return dados

        # Mesma regra das reservas: nada é agendado para trás.
        if data_inicio and hora_inicio:
            if datetime.combine(data_inicio, hora_inicio) < datetime.now():
                self.add_error(None, 'Não é possível criar um evento em data ou horário que já passou.')
                return dados

        # Conflito com outros eventos, pela janela real, e com reservas
        # aprovadas, pelas faixas da grade que o evento vai ocupar.
        if dados.get('sala') and data_inicio and data_fim and hora_inicio and hora_fim:
            provisorio = Evento(
                sala=dados['sala'],
                data_inicio=data_inicio,
                data_fim=data_fim,
                horario_inicio=hora_inicio,
                horario_fim=hora_fim,
            )
            conflitos = buscar_conflitos(provisorio, ignorar_evento=self.instance)
            if conflitos:
                self.add_error(None, mensagem_de_conflito(dados['sala'], conflitos))

        return dados
