from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required


@login_required
def dashboard(request):
    try:
        rola = request.user.profil.rola
    except Exception:
        rola = None

    if rola == 'admin':
        return redirect('/admin/')
    else:
        return redirect('pracownicy:lista')
