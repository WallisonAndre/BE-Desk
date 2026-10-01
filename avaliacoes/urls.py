from django.urls import path

from avaliacoes.views import avaliar_reserva, indicadores, minhas_avaliacoes

urlpatterns = [
    path("avaliacoes/", minhas_avaliacoes, name="minhas_avaliacoes"),
    path("avaliacoes/nova/<int:agendamento_id>/", avaliar_reserva, name="avaliar_reserva"),
    path("painel-admin/avaliacoes/", indicadores, name="indicadores_avaliacoes"),
]
