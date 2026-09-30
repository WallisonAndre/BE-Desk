"""Avaliação dos espaços por quem os usou."""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from bedesk.models import Agendamento

NOTAS = [
    (1, '1 - Ruim'),
    (2, '2 - Regular'),
    (3, '3 - Bom'),
    (4, '4 - Muito bom'),
    (5, '5 - Excelente'),
]


def _campo_de_nota(rotulo):
    return models.PositiveSmallIntegerField(
        choices=NOTAS,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=rotulo,
    )


class Avaliacao(models.Model):
    """Nota que o usuário dá ao espaço depois de usá-lo.

    A avaliação pertence à reserva, não à sala: ela é o registro de que
    alguém usou aquele espaço naquele horário e achou o que achou. Prender à
    reserva é o que garante que só avalia quem usou, uma vez por uso — a
    média do espaço sai da soma dessas notas.

    O dono e o espaço não são gravados de novo aqui: saem da reserva, que já
    os guarda. Copiá-los criaria dois lugares para a mesma verdade.
    """

    CRITERIOS = ['limpeza', 'estrutura', 'organizacao', 'conservacao']

    reserva = models.OneToOneField(
        Agendamento,
        on_delete=models.CASCADE,
        related_name='avaliacao',
        verbose_name='Reserva avaliada',
    )

    nota = _campo_de_nota('Nota geral')
    limpeza = _campo_de_nota('Limpeza')
    estrutura = _campo_de_nota('Estrutura')
    organizacao = _campo_de_nota('Organização')
    conservacao = _campo_de_nota('Conservação')

    comentario = models.TextField(
        blank=True,
        verbose_name='Comentário',
        help_text='Opcional. Conte o que estava bom ou o que precisa melhorar.',
    )

    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criada_em']
        verbose_name = 'Avaliação'
        verbose_name_plural = 'Avaliações'

    def __str__(self):
        return f'{self.sala.nome} — {self.nota} de 5, por {self.usuario.get_full_name() or self.usuario.username}'

    @property
    def sala(self):
        return self.reserva.sala

    @property
    def usuario(self):
        return self.reserva.usuario

    @property
    def media_criterios(self):
        """Média dos quatro critérios, com uma casa decimal."""
        notas = [getattr(self, criterio) for criterio in self.CRITERIOS]
        return round(sum(notas) / len(notas), 1)

    @property
    def estrelas(self):
        """Cinco posições, marcando quais estão preenchidas — a tela só desenha."""
        return [(posicao, posicao <= self.nota) for posicao in range(1, 6)]

    @property
    def notas_por_criterio(self):
        """Pares (rótulo, nota) para as telas listarem sem repetir nomes."""
        return [
            (self._meta.get_field(criterio).verbose_name, getattr(self, criterio))
            for criterio in self.CRITERIOS
        ]
