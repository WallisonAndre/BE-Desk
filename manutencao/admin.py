from django.contrib import admin

from manutencao.models import HistoricoManutencao, SolicitacaoManutencao


class HistoricoInline(admin.TabularInline):
    model = HistoricoManutencao
    extra = 0
    readonly_fields = ('autor', 'status_anterior', 'status_novo', 'observacao', 'criado_em')


@admin.register(SolicitacaoManutencao)
class SolicitacaoManutencaoAdmin(admin.ModelAdmin):
    list_display = ('id', 'local', 'categoria', 'prioridade', 'status', 'solicitante', 'criado_em')
    list_filter = ('status', 'prioridade', 'categoria')
    search_fields = ('descricao', 'outro_local', 'sala__nome', 'solicitante__username')
    inlines = [HistoricoInline]
