from datetime import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from bedesk.models import Agendamento, Sala


class Evento(models.Model):
    """Atividade programada num espaço do Bloco E.

    O espaço é reservado automaticamente: ao salvar, o evento gera
    agendamentos aprovados nos horários que ocupa (ver
    `eventos.services.reservar_espaco`), o que faz o evento aparecer na
    grade e impede que alguém reserve o mesmo horário.
    """

    PROGRAMADO = 'PROGRAMADO'
    CANCELADO = 'CANCELADO'

    STATUS_CHOICES = [
        (PROGRAMADO, 'Programado'),
        (CANCELADO, 'Cancelado'),
    ]

    CATEGORIA_CHOICES = [
        ('ESPORTIVO', 'Esportivo'),
        ('ACADEMICO', 'Acadêmico'),
        ('INSTITUCIONAL', 'Institucional'),
        ('OUTRO', 'Outro'),
    ]

    nome = models.CharField(max_length=150)
    descricao = models.TextField(verbose_name='Descrição')
    categoria = models.CharField(max_length=15, choices=CATEGORIA_CHOICES, default='OUTRO')

    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='eventos_responsavel',
        verbose_name='Responsável',
    )
    sala = models.ForeignKey(
        Sala,
        on_delete=models.PROTECT,
        related_name='eventos',
        verbose_name='Espaço utilizado',
    )

    data_inicio = models.DateField(verbose_name='Data de início')
    data_fim = models.DateField(verbose_name='Data de término')
    horario_inicio = models.TimeField(verbose_name='Horário de início')
    horario_fim = models.TimeField(verbose_name='Horário de término')

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=PROGRAMADO)

    # Agendamentos gerados para bloquear a grade. Guardados aqui para o
    # cancelamento conseguir liberar exatamente os horários que ocupou.
    agendamentos = models.ManyToManyField(Agendamento, blank=True, related_name='eventos')

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='eventos_criados',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['data_inicio', 'horario_inicio']
        verbose_name = 'Evento'
        verbose_name_plural = 'Eventos'
        indexes = [models.Index(fields=['status']), models.Index(fields=['data_inicio'])]

    def __str__(self):
        return f'{self.nome} — {self.sala.nome}'

    def clean(self):
        erros = {}
        if self.data_inicio and self.data_fim and self.data_fim < self.data_inicio:
            erros['data_fim'] = 'A data de término não pode ser anterior à de início.'
        if self.horario_inicio and self.horario_fim and self.horario_fim <= self.horario_inicio:
            erros['horario_fim'] = 'O horário de término deve ser depois do de início.'
        if erros:
            raise ValidationError(erros)

    def get_absolute_url(self):
        return reverse('detalhe_evento', args=[self.pk])

    @property
    def inicio(self):
        return datetime.combine(self.data_inicio, self.horario_inicio)

    @property
    def fim(self):
        return datetime.combine(self.data_fim, self.horario_fim)

    @property
    def encerrado(self):
        return self.fim < datetime.now()

    @property
    def cancelado(self):
        return self.status == self.CANCELADO

    @property
    def aberto_para_inscricao(self):
        return not self.cancelado and not self.encerrado

    @property
    def total_inscritos(self):
        return self.inscricoes.count()

    @property
    def dia_unico(self):
        return self.data_inicio == self.data_fim

    def inscricao_de(self, usuario):
        if not usuario.is_authenticated:
            return None
        return self.inscricoes.filter(usuario=usuario).first()


class InscricaoEvento(models.Model):
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name='inscricoes')
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='inscricoes_evento',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Uma inscrição por pessoa por evento; o banco garante mesmo que
        # dois cliques cheguem juntos.
        constraints = [
            models.UniqueConstraint(fields=['evento', 'usuario'], name='inscricao_unica_por_evento')
        ]
        ordering = ['criado_em']
        verbose_name = 'Inscrição'
        verbose_name_plural = 'Inscrições'

    def __str__(self):
        return f'{self.usuario} em {self.evento.nome}'
