from functools import wraps
from django.shortcuts import render, redirect
from django.contrib import messages


def _get_rola(user):
    try:
        return user.profil.rola
    except Exception:
        return None


def _brak_dostepu(request, komunikat):
    messages.error(request, komunikat)
    return render(request, 'konta/brak_dostepu.html', {'komunikat': komunikat}, status=403)


def wymaga_roli(*role):
    """Decorator dla function-based views. Niezalogowany → redirect na login.
    Zalogowany z błędną rolą → 403 (nie redirect).
    Przykład: @wymaga_roli('admin') lub @wymaga_roli('admin', 'hr')
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if _get_rola(request.user) not in role:
                return _brak_dostepu(
                    request,
                    f'Brak dostępu – wymagana rola: {", ".join(role)}.',
                )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def tylko_hr(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        rola = _get_rola(request.user)
        if rola not in ('hr', 'admin'):
            return _brak_dostepu(request, 'Brak dostępu – ta strona jest dostępna tylko dla roli HR.')
        return view_func(request, *args, **kwargs)
    return wrapper


def tylko_kierownik(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        rola = _get_rola(request.user)
        if rola not in ('kierownik', 'admin'):
            return _brak_dostepu(request, 'Brak dostępu – ta strona jest dostępna tylko dla roli Kierownika.')
        return view_func(request, *args, **kwargs)
    return wrapper


def hr_lub_kierownik(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        rola = _get_rola(request.user)
        if rola not in ('hr', 'kierownik', 'admin'):
            return _brak_dostepu(request, 'Brak dostępu – wymagane zalogowanie z odpowiednią rolą.')
        return view_func(request, *args, **kwargs)
    return wrapper
