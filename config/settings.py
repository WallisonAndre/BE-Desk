import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / ".env")

# SECRET_KEY é o nome que o docker-compose entrega; DJANGO_SECRET_KEY fica
# aceito para não quebrar quem já tinha o .env antigo.
SECRET_KEY = os.getenv("SECRET_KEY") or os.getenv("DJANGO_SECRET_KEY", "unsafe-secret-key")

# SECURITY WARNING: don't run with debug turned on in production!
# O default é True para o desenvolvimento seguir funcionando sem .env;
# em produção o .env precisa trazer DEBUG=False.
DEBUG = os.getenv("DEBUG", "True").strip().lower() not in ("false", "0", "no", "off")

# Lista separada por vírgula. "*" continua sendo o default de desenvolvimento.
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "*").split(",") if h.strip()]

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
# SUAP OAuth2 Settings
SUAP_OAUTH_CLIENT_ID = os.getenv("SUAP_OAUTH_CLIENT_ID", "")
SUAP_OAUTH_CLIENT_SECRET = os.getenv("SUAP_OAUTH_CLIENT_SECRET", "")
SUAP_OAUTH_REDIRECT_URI = os.getenv("SUAP_OAUTH_REDIRECT_URI", BASE_URL + "/login/a/")
SUAP_API_URL = os.getenv("SUAP_API_URL", "https://suap.ifrn.edu.br")

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
    'usuarios',
    'reservas',
    'eventos',
    'notificacoes',
    'relatorios',
    'integracao_suap',
    'bedesk',
    'blog',
    'widget_tweaks',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'notificacoes.context_processors.notificacoes_pendentes',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

if os.getenv("POSTGRES_DB"):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv("POSTGRES_DB"),
            'USER': os.getenv("POSTGRES_USER", ""),
            'PASSWORD': os.getenv("POSTGRES_PASSWORD", ""),
            'HOST': os.getenv("DB_HOST", "db"),
            'PORT': os.getenv("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_REDIRECT_URL = '/'

LOGOUT_REDIRECT_URL = '/'

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Media files (uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
