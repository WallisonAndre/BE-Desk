import datetime

from django import forms

from bedesk.models import Agendamento


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

        if sala and data_inicio and horario:
            data_do_agendamento = data_inicio.date()
            # Só o que está aprovado ocupa o horário. Vários alunos podem pedir
            # o mesmo horário; quem aprova é que escolhe um e recusa os outros.
            conflitos = Agendamento.objects.filter(
                sala=sala,
                data_inicio__date=data_do_agendamento,
                horario=horario,
                status="APROVADO",
            )
            if self.instance and self.instance.pk:
                conflitos = conflitos.exclude(pk=self.instance.pk)
            if conflitos.exists():
                self.add_error(
                    None,
                    f"A sala {sala.nome} já tem uma reserva aprovada para as {horario.strftime('%H:%M')} de {data_do_agendamento.strftime('%d/%m/%Y')}. Escolha outro horário.",
                )
        return cleaned_data
