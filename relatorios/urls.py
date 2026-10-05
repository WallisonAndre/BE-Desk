from django.urls import path

from relatorios.views.avaliacoes import exportar_comentarios, exportar_medias

urlpatterns = [
    path(
        'painel-admin/avaliacoes/medias.csv',
        exportar_medias,
        name='exportar_medias_de_avaliacao',
    ),
    path(
        'painel-admin/avaliacoes/comentarios.csv',
        exportar_comentarios,
        name='exportar_comentarios_de_avaliacao',
    ),
]
