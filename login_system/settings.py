from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-9!kty10__n-t_tk2lh$2r(mdc9mxpx0bt2prrtgrw7zt8qagcx'

DEBUG = True

ALLOWED_HOSTS = []


# 🔥 APLICACIONES
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'loginApp',  # 👈 TU APP
]


# 🔧 MIDDLEWARE (NO TOCAR)
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'login_system.urls'


# 🧾 TEMPLATES (IMPORTANTE)
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # 👈 PARA HTML
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'login_system.wsgi.application'


# ❌ NO USAMOS ESTO (pero se deja por defecto)
DATABASES = {
    'default': {
        'ENGINE': 'mssql',
        'NAME': 'proyectoinformatico',
        'HOST': 'localhost',
        'OPTIONS': {
            'driver': 'ODBC Driver 17 for SQL Server',
            'trusted_connection': 'yes',
        },
    }
}


# 🔒 VALIDACIONES (NO TOCAR)
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


# 🌎 CONFIGURACIÓN LOCAL (MEJOR PARA CHILE)
LANGUAGE_CODE = 'es-cl'
TIME_ZONE = 'America/Santiago'

USE_I18N = True
USE_TZ = True


# 📁 ARCHIVOS ESTÁTICOS
STATIC_URL = 'static/'
STATICFILES_DIRS = [
    BASE_DIR / 'loginApp' / 'static',
]


# 🔑 CLAVE PRIMARIA
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# 📧 CONFIGURACIÓN EMAIL
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True

EMAIL_HOST_USER = 'franco.xd2015@gmail.com'
EMAIL_HOST_PASSWORD = 'ptlakjfyylgavkrl'