"""Exportação das avaliações em CSV, para levar os números para fora da tela."""

import csv

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse

from avaliacoes.models import Avaliacao
from avaliacoes.services import medias_por_espaco
from usuarios.permissions import is_admin_or_staff

# Planilha em português: separador ponto e vírgula e decimal com vírgula, que
# é como o Excel pt-BR espera. Com vírgula nos dois papéis, cada nota quebraria
# em duas colunas.
SEPARADOR = ';'


def _numero(valor):
    """4.6 -> '4,6'. Vazio quando não há nota."""
    if valor is None:
        return ''
    return f'{valor:.1f}'.replace('.', ',')


def _resposta_csv(nome_do_arquivo):
    """Resposta com BOM: sem ele o Excel abre 'Ginásio' como 'GinÃ¡sio'."""
    # O BOM é escrito à mão, logo abaixo. Declarar utf-8-sig aqui faria o
    # próprio Django acrescentar outro, e o Excel mostraria lixo na
    # primeira célula.
    resposta = HttpResponse(content_type='text/csv; charset=utf-8')
    resposta['Content-Disposition'] = f'attachment; filename="{nome_do_arquivo}"'
    resposta.write('﻿')
    return resposta


@login_required
@user_passes_test(is_admin_or_staff)
def exportar_medias(request):
    """Uma linha por espaço, com a nota geral e a de cada critério."""
    resposta = _resposta_csv('avaliacoes-medias.csv')
    escritor = csv.writer(resposta, delimiter=SEPARADOR)
    escritor.writerow([
        'Espaço', 'Nota geral', 'Limpeza', 'Estrutura', 'Organização',
        'Conservação', 'Avaliações',
    ])

    for linha in medias_por_espaco():
        # A chave do nome muda quando o PR #34 (issue #29) entrar: lá o
        # serviço passa a devolver 'nome'. Aceitar as duas evita que a
        # exportação quebre em silêncio dependendo da ordem dos merges.
        nome = linha.get('nome') or linha['reserva__sala__nome']
        escritor.writerow([
            nome,
            _numero(linha['media']),
            _numero(linha['media_limpeza']),
            _numero(linha['media_estrutura']),
            _numero(linha['media_organizacao']),
            _numero(linha['media_conservacao']),
            linha['total'],
        ])
    return resposta


@login_required
@user_passes_test(is_admin_or_staff)
def exportar_comentarios(request):
    """Um comentário por linha, respeitando o filtro de espaço da tela."""
    comentarios = (
        Avaliacao.objects.exclude(comentario='')
        .select_related('reserva', 'reserva__sala', 'reserva__usuario')
    )

    sala_escolhida = request.GET.get('sala') or ''
    if sala_escolhida.isdigit():
        comentarios = comentarios.filter(reserva__sala_id=int(sala_escolhida))

    resposta = _resposta_csv('avaliacoes-comentarios.csv')
    escritor = csv.writer(resposta, delimiter=SEPARADOR)
    escritor.writerow([
        'Espaço', 'Data do uso', 'Data da avaliação', 'Autor', 'Nota',
        'Limpeza', 'Estrutura', 'Organização', 'Conservação', 'Comentário',
    ])

    for avaliacao in comentarios:
        autor = avaliacao.usuario
        escritor.writerow([
            avaliacao.sala.nome,
            avaliacao.reserva.data_inicio.strftime('%d/%m/%Y') if avaliacao.reserva.data_inicio else '',
            avaliacao.criada_em.strftime('%d/%m/%Y'),
            autor.get_full_name() or autor.username,
            avaliacao.nota,
            avaliacao.limpeza,
            avaliacao.estrutura,
            avaliacao.organizacao,
            avaliacao.conservacao,
            avaliacao.comentario,
        ])
    return resposta
