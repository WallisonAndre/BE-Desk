from django.urls import path

from eventos.views.eventos import (
    cancelar_evento,
    cancelar_inscricao,
    criar_evento,
    detalhe_evento,
    editar_evento,
    inscrever,
    lista_eventos,
    participantes,
    remover_participante,
)

urlpatterns = [
    path("eventos/", lista_eventos, name="lista_eventos"),
    path("eventos/novo/", criar_evento, name="criar_evento"),
    path("eventos/<int:pk>/", detalhe_evento, name="detalhe_evento"),
    path("eventos/<int:pk>/editar/", editar_evento, name="editar_evento"),
    path("eventos/<int:pk>/cancelar/", cancelar_evento, name="cancelar_evento"),
    path("eventos/<int:pk>/inscrever/", inscrever, name="inscrever_evento"),
    path("eventos/<int:pk>/sair/", cancelar_inscricao, name="cancelar_inscricao_evento"),
    path("eventos/<int:pk>/participantes/", participantes, name="participantes_evento"),
    path(
        "eventos/<int:pk>/participantes/<int:inscricao_id>/remover/",
        remover_participante,
        name="remover_participante_evento",
    ),
]
