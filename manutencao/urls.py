from django.urls import path

from manutencao.views.solicitacoes import (
    atualizar_status,
    criar_solicitacao,
    detalhe_solicitacao,
    minhas_solicitacoes,
    painel_manutencao,
)

urlpatterns = [
    path("manutencao/", minhas_solicitacoes, name="minhas_manutencoes"),
    path("manutencao/nova/", criar_solicitacao, name="criar_manutencao"),
    path("manutencao/painel/", painel_manutencao, name="painel_manutencao"),
    path("manutencao/<int:pk>/", detalhe_solicitacao, name="detalhe_manutencao"),
    path("manutencao/<int:pk>/atualizar/", atualizar_status, name="atualizar_manutencao"),
]
