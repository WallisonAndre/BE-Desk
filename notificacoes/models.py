from django.conf import settings
from django.db import models
from django.urls import reverse


class Notificacao(models.Model):
    TIPO_CHOICES = [
        ('RESERVA_CRIADA', 'Reserva criada'),
        ('RESERVA_APROVADA', 'Reserva aprovada'),
        ('RESERVA_REJEITADA', 'Reserva rejeitada'),
        ('RESERVA_CANCELADA', 'Reserva cancelada'),
        ('MANUTENCAO_CRIADA', 'Solicitação de manutenção'),
        ('MANUTENCAO_ATUALIZADA', 'Manutenção atualizada'),
        ('MANUTENCAO_RESOLVIDA', 'Manutenção concluída'),
        ('LEMBRETE', 'Lembrete'),
        ('ADMIN_NOVA_SOLICITACAO', 'Nova solicitação'),
        ('CONFLITO_HORARIO', 'Conflito de horário'),
        ('SISTEMA', 'Sistema'),
    ]

    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notificacoes',
    )
    titulo = models.CharField(max_length=200)
    mensagem = models.TextField()
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, default='SISTEMA')
    link = models.CharField(max_length=300, blank=True, default='')
    lida = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criada_em']
        verbose_name = 'Notificação'
        verbose_name_plural = 'Notificações'

    def __str__(self):
        return f"[{self.tipo}] {self.titulo} → {self.destinatario.username}"

    def get_absolute_url(self):
        if self.link:
            return self.link
        return reverse('notificacoes_lista')

    @property
    def icone(self):
        icons = {
            'RESERVA_CRIADA': 'fa-calendar-plus',
            'RESERVA_APROVADA': 'fa-calendar-check',
            'RESERVA_REJEITADA': 'fa-calendar-xmark',
            'RESERVA_CANCELADA': 'fa-calendar-minus',
            'MANUTENCAO_CRIADA': 'fa-screwdriver-wrench',
            'MANUTENCAO_ATUALIZADA': 'fa-wrench',
            'MANUTENCAO_RESOLVIDA': 'fa-circle-check',
            'LEMBRETE': 'fa-bell',
            'ADMIN_NOVA_SOLICITACAO': 'fa-user-plus',
            'CONFLITO_HORARIO': 'fa-clock-rotate-left',
            'SISTEMA': 'fa-circle-info',
        }
        return icons.get(self.tipo, 'fa-bell')

    @property
    def cor(self):
        colors = {
            'RESERVA_CRIADA': '#3b82f6',
            'RESERVA_APROVADA': '#22c55e',
            'RESERVA_REJEITADA': '#ef4444',
            'RESERVA_CANCELADA': '#f59e0b',
            'MANUTENCAO_CRIADA': '#f97316',
            'MANUTENCAO_ATUALIZADA': '#0ea5e9',
            'MANUTENCAO_RESOLVIDA': '#22c55e',
            'LEMBRETE': '#8b5cf6',
            'ADMIN_NOVA_SOLICITACAO': '#f59e0b',
            'CONFLITO_HORARIO': '#ef4444',
            'SISTEMA': '#6b7280',
        }
        return colors.get(self.tipo, '#6b7280')
