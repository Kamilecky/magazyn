from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from .models import Notatka


# Wspólna funkcja pomocnicza — renderuje listę notatek jako HTML i zwraca jako JSON
# Używana po każdej operacji (dodaj/usuń), aby odświeżyć panel boczny bez przeładowania strony
def _lista_response(request):
    notatki = Notatka.objects.select_related('autor').all()
    html = render_to_string('notatki/_lista.html', {'notatki': notatki}, request=request)
    return JsonResponse({'html': html, 'liczba': notatki.count()})


# GET /notatki/ — zwraca aktualną listę notatek jako HTML w JSON (odpytywane przez AJAX)
@login_required
def lista(request):
    return _lista_response(request)


# POST /notatki/dodaj/ — tworzy nową notatkę i zwraca odświeżoną listę
@login_required
@require_POST
def dodaj(request):
    tresc = (request.POST.get('tresc') or '').strip()
    # Pusta treść jest ignorowana — nie tworzy pustej notatki
    if tresc:
        Notatka.objects.create(tresc=tresc, autor=request.user)
    return _lista_response(request)


# POST /notatki/<pk>/usun/ — usuwa notatkę i zwraca odświeżoną listę
@login_required
@require_POST
def usun(request, pk):
    # filter().delete() zamiast get_object_or_404 — brak wyjątku gdy notatka już usunięta
    Notatka.objects.filter(pk=pk).delete()
    return _lista_response(request)
