import json
from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


@register.filter
def kompetencje_json(komp_lista):
    return json.dumps(
        [{'n': k.aktywnosc.nazwa, 'd': k.aktywnosc.dzial, 'v': round(float(k.wynik), 2)}
         for k in (komp_lista or [])],
        ensure_ascii=False,
    )
