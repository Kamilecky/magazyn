from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from .models import Notatka


def _lista_response(request):
    notatki = Notatka.objects.select_related('autor').all()
    html = render_to_string('notatki/_lista.html', {'notatki': notatki}, request=request)
    return JsonResponse({'html': html, 'liczba': notatki.count()})


@login_required
def lista(request):
    return _lista_response(request)


@login_required
@require_POST
def dodaj(request):
    tresc = (request.POST.get('tresc') or '').strip()
    if tresc:
        Notatka.objects.create(tresc=tresc, autor=request.user)
    return _lista_response(request)


@login_required
@require_POST
def usun(request, pk):
    Notatka.objects.filter(pk=pk).delete()
    return _lista_response(request)
