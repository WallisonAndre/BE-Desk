import datetime

from django import forms

from bedesk.models import Agendamento, Sala
from reservas.models import HorarioFixo
from reservas.views.salas import FAIXAS_HORARIO, horario_fixo_em

# A checagem de conflito compara o horário exato. Uma reserva fora destes
# inícios — 14:10, por exemplo — não colidiria com nada e passaria por cima
# de outra reserva ou de um evento.
INICIOS_DA_GRADE = {inicio for inicio, _ in FAIXAS_HORARIO}


def reserva_em_conflito(sala, dia, horario, excluir_pk=None):
    """Reserva aprovada que já ocupa a sala no dia e horário.

    Pedido pendente não ocupa: vários alunos podem pedir o mesmo horário, e
    quem aprova escolhe um e recusa os outros. A trava contra duas aprovações
    no mesmo horário fica em core.views.dashboard.mudar_status_reserva.
    """
    agendamentos = Agendamento.objects.filter(
        sala=sala,
        data_inicio__date=dia,
        horario=horario,
        status="APROVADO",
    )
    if excluir_pk:
        agendamentos = agendamentos.exclude(pk=excluir_pk)
    return agendamentos.first()


def mensagem_horario_fixo(sala, horario_fixo, horario):
    return (
        f"A sala {sala.nome} tem horário fixo às {horario.strftime('%H:%M')} toda "
        f"{horario_fixo.get_dia_semana_display().lower()}: {horario_fixo.descricao}. "
        "Escolha outro horário."
    )


def mensagem_reserva_em_conflito(sala, dia, horario):
    return (
        f"A sala {sala.nome} já tem uma reserva aprovada para as "
        f"{horario.strftime('%H:%M')} de {dia.strftime('%d/%m/%Y')}. Escolha outro horário."
    )


class AgendarForm(forms.ModelForm):
    class Meta:
        model = Agendamento
        fields = ["nome", "sala", "motivo", "horario", "data_inicio"]
        labels = {
            "nome": "Título da Reserva",
            "sala": "Sala",
            "motivo": "Motivo da Reserva",
            "horario": "Horário de Início",
            "data_inicio": "Data",
        }

    def clean(self):
        cleaned_data = super().clean()
        sala = cleaned_data.get("sala")
        horario = cleaned_data.get("horario")
        data_inicio = cleaned_data.get("data_inicio")
        horario_abertura = datetime.time(7, 0)
        horario_fechamento = datetime.time(18, 0)

        if horario and (horario < horario_abertura or horario > horario_fechamento):
            self.add_error(
                "horario",
                f"O horário deve estar entre {horario_abertura.strftime('%H:%M')} e {horario_fechamento.strftime('%H:%M')}.",
            )
            return cleaned_data

        if horario and horario not in INICIOS_DA_GRADE:
            # Erro geral, não do campo: quando o horário vem da grade ele é
            # renderizado oculto, e o erro de um campo oculto não aparece.
            self.add_error(None, "Escolha um dos horários da grade da sala.")
            return cleaned_data

        if sala and data_inicio and horario:
            dia = data_inicio.date()
            fixo = horario_fixo_em(sala, dia, horario)
            if fixo:
                self.add_error(None, mensagem_horario_fixo(sala, fixo, horario))
                return cleaned_data
            if reserva_em_conflito(sala, dia, horario, excluir_pk=self.instance.pk):
                self.add_error(None, mensagem_reserva_em_conflito(sala, dia, horario))
        return cleaned_data


class HorarioFixoForm(forms.ModelForm):
    class Meta:
        model = HorarioFixo
        fields = ["sala", "dia_semana", "horario_inicio", "horario_fim", "descricao"]
        widgets = {
            "horario_inicio": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "horario_fim": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "descricao": forms.TextInput(
                attrs={"placeholder": "Ex.: Treino de futsal da equipe do campus"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sala"].queryset = Sala.objects.order_by("nome")
        for campo in ("horario_inicio", "horario_fim"):
            self.fields[campo].input_formats = ["%H:%M", "%H:%M:%S"]
