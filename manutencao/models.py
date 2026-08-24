from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from bedesk.models import Sala


class SolicitacaoManutencao(models.Model):
    """Problema de infraestrutura relatado num espaço do Bloco E."""

    ABERTA = 'ABERTA'
    EM_ANALISE = 'EM_ANALISE'
    EM_MANUTENCAO = 'EM_MANUTENCAO'
    RESOLVIDA = 'RESOLVIDA'

    STATUS_CHOICES = [
        (ABERTA, 'Aberta'),
        (EM_ANALISE, 'Em análise'),
        (EM_MANUTENCAO, 'Em manutenção'),
        (RESOLVIDA, 'Resolvida'),
    ]

    # Status que ainda demandam ação da administração.
    STATUS_ABERTOS = [ABERTA, EM_ANALISE, EM_MANUTENCAO]

    CATEGORIA_CHOICES = [
        ('ELETRICA', 'Elétrica'),
        ('HIDRAULICA', 'Hidráulica'),
        ('ESTRUTURAL', 'Estrutural'),
        ('EQUIPAMENTO', 'Equipamento'),
        ('ILUMINACAO', 'Iluminação'),
        ('LIMPEZA', 'Limpeza'),
        ('OUTRO', 'Outro'),
    ]

    PRIORIDADE_CHOICES = [
        ('BAIXA', 'Baixa'),
        ('MEDIA', 'Média'),
        ('ALTA', 'Alta'),
        ('URGENTE', 'Urgente'),
    ]

    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='solicitacoes_manutencao',
    )

    # O espaço pode ser um local cadastrado ou, para "outros espaços",
    # um texto livre — nem todo canto do bloco é uma Sala reservável.
    sala = models.ForeignKey(
        Sala,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='solicitacoes_manutencao',
        verbose_name='Espaço',
    )
    outro_local = models.CharField(
        max_length=120,
        blank=True,
        verbose_name='Outro espaço',
        help_text='Preencha apenas se o espaço não estiver na lista acima.',
    )

    categoria = models.CharField(
        max_length=20,
        choices=CATEGORIA_CHOICES,
        default='OUTRO',
        verbose_name='Categoria do problema',
    )
    descricao = models.TextField(
        verbose_name='Descrição do problema',
        help_text='Explique o que está acontecendo e onde exatamente.',
    )
    imagem = models.ImageField(
        upload_to='manutencao/',
        blank=True,
        null=True,
        verbose_name='Foto do problema',
        help_text='Opcional, mas ajuda muito na avaliação.',
    )

    prioridade = models.CharField(
        max_length=10,
        choices=PRIORIDADE_CHOICES,
        default='MEDIA',
    )
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default=ABERTA,
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    resolvido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Solicitação de manutenção'
        verbose_name_plural = 'Solicitações de manutenção'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['prioridade']),
        ]

    def __str__(self):
        return f'#{self.pk} — {self.local} ({self.get_status_display()})'

    def clean(self):
        if not self.sala and not self.outro_local.strip():
            raise ValidationError({
                'sala': 'Escolha um espaço da lista ou descreva em "Outro espaço".'
            })

    def get_absolute_url(self):
        return reverse('detalhe_manutencao', args=[self.pk])

    @property
    def local(self):
        """Nome do espaço, venha ele da lista ou do texto livre."""
        return self.sala.nome if self.sala else (self.outro_local or 'Espaço não informado')

    @property
    def aberta(self):
        return self.status in self.STATUS_ABERTOS

    @property
    def status_cor(self):
        return {
            self.ABERTA: 'is-aberta',
            self.EM_ANALISE: 'is-analise',
            self.EM_MANUTENCAO: 'is-manutencao',
            self.RESOLVIDA: 'is-resolvida',
        }.get(self.status, 'is-aberta')

    @property
    def prioridade_cor(self):
        return {
            'BAIXA': 'is-baixa',
            'MEDIA': 'is-media',
            'ALTA': 'is-alta',
            'URGENTE': 'is-urgente',
        }.get(self.prioridade, 'is-media')


class HistoricoManutencao(models.Model):
    """Registro de cada mudança de status, com a observação de quem mexeu.

    Mantido em tabela própria para o histórico sobreviver a novas
    alterações — guardar só o último estado perderia o percurso.
    """

    solicitacao = models.ForeignKey(
        SolicitacaoManutencao,
        on_delete=models.CASCADE,
        related_name='historico',
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='alteracoes_manutencao',
    )
    status_anterior = models.CharField(
        max_length=15,
        choices=SolicitacaoManutencao.STATUS_CHOICES,
        blank=True,
    )
    status_novo = models.CharField(
        max_length=15,
        choices=SolicitacaoManutencao.STATUS_CHOICES,
    )
    observacao = models.TextField(
        blank=True,
        verbose_name='Observação',
        help_text='O que foi verificado ou resolvido.',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Registro de manutenção'
        verbose_name_plural = 'Histórico de manutenção'

    def __str__(self):
        return f'{self.solicitacao_id}: {self.status_anterior or "—"} → {self.status_novo}'
