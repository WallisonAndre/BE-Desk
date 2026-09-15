"""Serialização das escritas que ocupam horários de uma sala.

Conferir o conflito e só depois gravar deixa uma janela em que duas
requisições simultâneas passam pela mesma checagem e gravam as duas. Travar
a linha da sala dentro da transação faz essas requisições entrarem uma de
cada vez: a segunda só confere o conflito depois que a primeira gravou.
"""

from bedesk.models import Sala


def travar_sala(sala_id):
    """Trava a sala até o fim da transação atual.

    Precisa ser chamada dentro de transaction.atomic(). No PostgreSQL de
    produção vira SELECT ... FOR UPDATE. O SQLite de desenvolvimento ignora a
    trava, então ali a proteção contra corrida não vale.
    """
    return Sala.objects.select_for_update().get(pk=sala_id)
