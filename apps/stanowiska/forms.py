from django import forms
from .models import Stanowisko


class StanowiskoForm(forms.ModelForm):
    class Meta:
        model = Stanowisko
        fields = [
            'nazwa', 'opis', 'aktywne', 'max_pracownikow',
            'wymagana_sila_kg', 'zakres_dzwigania',
            'poziom_chodzenia', 'poziom_siedzenia', 'powtarzalnosc_czynnosci',
            'praca_stojaca', 'praca_przy_monitorze', 'wymaga_komputera', 'praca_na_zewnatrz',
        ]
        widgets = {
            'nazwa': forms.TextInput(attrs={'class': 'form-control'}),
            'opis': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'max_pracownikow': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'wymagana_sila_kg': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'zakres_dzwigania': forms.Select(attrs={'class': 'form-select'}),
            'poziom_chodzenia': forms.Select(attrs={'class': 'form-select'}),
            'poziom_siedzenia': forms.Select(attrs={'class': 'form-select'}),
            'powtarzalnosc_czynnosci': forms.Select(attrs={'class': 'form-select'}),
            'aktywne': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'praca_stojaca': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'praca_przy_monitorze': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'wymaga_komputera': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'praca_na_zewnatrz': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
