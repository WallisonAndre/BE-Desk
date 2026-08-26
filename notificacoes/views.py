from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render

from .models import Notificacao


def _json_login_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'unauthorized', 'notifications': [], 'unread': 0}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
def notificacoes_lista(request):
    notificacoes = list(Notificacao.objects.filter(destinatario=request.user)[:30])

    # Abrir a lista conta como ter visto: zera o contador do sininho.
    # As não lidas são marcadas só depois de carregadas, para esta
    # visita ainda exibir o destaque de "nova" antes de sumir.
    Notificacao.objects.filter(destinatario=request.user, lida=False).update(lida=True)

    return render(request, 'notificacoes/lista.html', {
        'notificacoes': notificacoes,
    })


@_json_login_required
def notificacoes_api(request):
    notificacoes = Notificacao.objects.filter(destinatario=request.user)[:15]
    data = [{
        'id': n.id,
        'titulo': n.titulo,
        'mensagem': n.mensagem,
        'tipo': n.tipo,
        'icone': n.icone,
        'cor': n.cor,
        'link': n.get_absolute_url(),
        'lida': n.lida,
        'criada_em': n.criada_em.isoformat(),
    } for n in notificacoes]
    nao_lidas = Notificacao.objects.filter(destinatario=request.user, lida=False).count()
    return JsonResponse({'notifications': data, 'unread': nao_lidas})


@login_required
def marcar_como_lida(request, notificacao_id):
    try:
        notif = Notificacao.objects.get(id=notificacao_id, destinatario=request.user)
        notif.lida = True
        notif.save()
    except Notificacao.DoesNotExist:
        pass

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True})

    redirect_url = request.GET.get('next', '/')
    return redirect(redirect_url)


@login_required
def marcar_todas_lidas(request):
    Notificacao.objects.filter(destinatario=request.user, lida=False).update(lida=True)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True})

    return redirect('notificacoes_lista')
