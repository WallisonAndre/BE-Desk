from django.contrib import admin

from eventos.models import Evento, InscricaoEvento


class InscricaoInline(admin.TabularInline):
    model = InscricaoEvento
    extra = 0
    readonly_fields = ('criado_em',)


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'sala', 'data_inicio', 'horario_inicio', 'status', 'responsavel')
    list_filter = ('status', 'categoria', 'sala')
    search_fields = ('nome', 'descricao', 'sala__nome')
    inlines = [InscricaoInline]
