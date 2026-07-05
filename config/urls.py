from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', lambda request: redirect('konta:dashboard'), name='home'),
    path('konta/login/', auth_views.LoginView.as_view(), name='login'),
    path('konta/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('konta/', include('apps.konta.urls')),
path('przydzialy/', include('apps.przydzialy.urls')),
    path('raporty/', include('apps.raporty.urls')),
    path('pracownicy/', include('apps.pracownicy.urls')),
    path('import/', include(('apps.pracownicy.urls_import', 'import_danych'))),
    path('notatki/', include('apps.notatki.urls')),
]

handler404 = 'config.views.error_404'
handler500 = 'config.views.error_500'
