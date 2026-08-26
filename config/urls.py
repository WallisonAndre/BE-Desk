from django.contrib import admin
from django.urls import include, path
from usuarios.views.accounts import logar
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    # Override the default login view to use our custom SUAP integration
    path("accounts/login/", logar, name="login"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("core.urls")),
    path("", include("usuarios.urls")),
    path("", include("reservas.urls")),
    path("", include("manutencao.urls")),
    path("", include("eventos.urls")),
    path("", include("notificacoes.urls")),
    path("", include("relatorios.urls")),
    path("", include("integracao_suap.urls")),
    path("", include("blog.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
