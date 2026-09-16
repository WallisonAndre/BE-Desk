"""Ocupações recorrentes da grade de horários."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from bedesk.models import Sala


class HorarioFixo(models.Model):
    """Uso recorrente de um espaço, sempre no mesmo dia da semana e horário.

    Treinos e atividades regulares não passam por pedido de reserva: ocupam a
    grade toda semana, sem data de fim. Por isso o horário fixo não gera
    agendamento nenhum — a grade e as checagens de conflito consultam este
    modelo direto, e remover o registro libera o horário na hora.
    """

    SEGUNDA = 0
    DIAS_SEMANA = [
        (SEGUNDA, 'Segunda-feira'),
        (1, 'Terça-feira'),
        (2, 'Quarta-feira'),
        (3, 'Quinta-feira'),
        (4, 'Sexta-feira'),
    ]

    sala = models.ForeignKey(
        Sala,
        on_delete=models.PROTECT,
        related_name='horarios_fixos',
        verbose_name='Espaço',
    )
    dia_semana = models.PositiveSmallIntegerField(
        choices=DIAS_SEMANA,
        verbose_name='Dia da semana',
    )
    horario_inicio = models.TimeField(verbose_name='Horário de início')
    horario_fim = models.TimeField(verbose_name='Horário de término')
    descricao = models.CharField(
        max_length=150,
        verbose_name='O que ocupa',
        help_text='Ex.: Treino de futsal da equipe do campus',
    )

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='horarios_fixos_criados',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sala__nome', 'dia_semana', 'horario_inicio']
        verbose_name = 'Horário fixo'
        verbose_name_plural = 'Horários fixos'
        constraints = [
            models.UniqueConstraint(
                fields=['sala', 'dia_semana', 'horario_inicio'],
                name='horario_fixo_unico_por_sala_dia_e_inicio',
            )
        ]
        indexes = [models.Index(fields=['sala', 'dia_semana'])]

    def __str__(self):
        return f'{self.descricao} — {self.sala.nome}, {self.get_dia_semana_display()}'

    def clean(self):
        # Import local: reservas.views.salas é quem guarda a estrutura da grade,
        # e importar no topo criaria ciclo quando a view passar a usar o modelo.
        from reservas.views.salas import FAIXAS_HORARIO

        if self.horario_inicio and self.horario_fim and self.horario_fim <= self.horario_inicio:
            raise ValidationError(
                {'horario_fim': 'O horário de término deve ser depois do de início.'}
            )

        if self.horario_inicio and self.horario_fim:
            toca_a_grade = any(
                inicio < self.horario_fim and fim > self.horario_inicio
                for inicio, fim in FAIXAS_HORARIO
            )
            if not toca_a_grade:
                primeiro, ultimo = FAIXAS_HORARIO[0][0], FAIXAS_HORARIO[-1][1]
                raise ValidationError(
                    'O horário fixo precisa cair dentro da grade da sala, que hoje vai '
                    f'das {primeiro:%H:%M} às {ultimo:%H:%M}, de segunda a sexta.'
                )

    @property
    def periodo(self):
        return f'{self.horario_inicio:%H:%M} às {self.horario_fim:%H:%M}'
