from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required


# Przekierowanie po zalogowaniu — zależne od roli użytkownika
@login_required
def dashboard(request):
    # Odczytaj rolę z profilu; try/except zabezpiecza gdy profil nie istnieje
    try:
        rola = request.user.profil.rola
    except Exception:
        rola = None

    # Admin trafia do panelu administracyjnego Django (/admin/)
    if rola == 'admin':
        return redirect('/admin/')
    # HR i kierownik trafiają na listę pracowników
    else:
        return redirect('pracownicy:lista')
