from django.urls import path

from reservas.views.ajax import (
    criar_agendamento,
    deletar_agendamento,
    editar_agendamento,
    lista_agendamentos,
    tela_ajax,
)
from reservas.views.horarios_fixos import (
    criar_horario_fixo,
    editar_horario_fixo,
    lista_horarios_fixos,
    remover_horario_fixo,
)
from reservas.views.reservas import agendar_sala, cancelar_reserva_usuario, lista_reservas
from reservas.views.salas import detalhe_sala, lista_locais

urlpatterns = [
    path("crud/", tela_ajax, name="crud_ajax"),
    path("agendamentos/", lista_agendamentos, name="lista_agendamentos"),
    path("agendamentos/criar/", criar_agendamento, name="criar_agendamento"),
    path("agendamentos/<int:id>/editar/", editar_agendamento, name="editar_agendamento"),
    path("agendamentos/<int:id>/deletar/", deletar_agendamento, name="deletar_agendamento"),
    path("locais/", lista_locais, name="lista_locais"),
    path("sala/<str:nome_sala>/", detalhe_sala, name="detalhe_sala"),
    path("agendar/", agendar_sala, name="agendar_sala"),
    path("reservas/", lista_reservas, name="lista_reserva"),
    path("horarios-fixos/", lista_horarios_fixos, name="lista_horarios_fixos"),
    path("horarios-fixos/novo/", criar_horario_fixo, name="criar_horario_fixo"),
    path("horarios-fixos/<int:pk>/editar/", editar_horario_fixo, name="editar_horario_fixo"),
    path("horarios-fixos/<int:pk>/remover/", remover_horario_fixo, name="remover_horario_fixo"),
    path(
        "reservas/cancelar/<int:agendamento_id>/",
        cancelar_reserva_usuario,
        name="cancelar_reserva_usuario",
    ),
]
