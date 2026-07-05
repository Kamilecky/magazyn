from django import forms


class ImportPlanZmianowego(forms.Form):
    plik = forms.FileField(
        label='Plik planu (.xlsx)',
        help_text='Plik Plan_dzienny_NEW.xlsx — arkusz „PLAN NEW" z 3 zmianami w jednym arkuszu.',
    )


class ImportPracownikow(forms.Form):
    plik_kompetencje = forms.FileField(
        required=False,
        label='Plik kompetencji (.xlsx)',
        help_text='KOMPETENCJE_PRACOWNIKÓW_ACT_NEW.xlsx — arkusz „Wynik finalny" z macierzą kompetencji.',
    )
    plik_struktura = forms.FileField(
        required=False,
        label='Plik struktury/grafiku (.xlsx)',
        help_text='Struktura___Grafik___Absencje_NEW.xlsx — arkusze per dział z grafikiem i absencjami.',
    )

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('plik_kompetencje') and not cleaned.get('plik_struktura'):
            raise forms.ValidationError('Wybierz co najmniej jeden plik (kompetencji lub struktury).')
        return cleaned


class ImportPracownikowAPT(forms.Form):
    plik = forms.FileField(
        label='Plik pracowników APT (.xlsx)',
        help_text='PracownicyAPT_list_ver_02_NEW.xlsx — lista pracowników agencyjnych.',
    )
