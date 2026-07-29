from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from apps.konta.models import Profil


def _make_user(username, rola, password='testpass123'):
    user = User.objects.create_user(username=username, password=password)
    Profil.objects.create(uzytkownik=user, rola=rola)
    return user


class UsunWszystkichAccessTest(TestCase):
    """usun_wszystkich: tylko admin może wykonać akcję."""

    def setUp(self):
        self.client = Client()
        self.url = reverse('pracownicy:usun_wszystkich')
        self.admin = _make_user('admin_test', 'admin')
        self.hr = _make_user('hr_test', 'hr')
        self.kierownik = _make_user('kierownik_test', 'kierownik')

    def test_admin_moze_wywolac(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url)
        self.assertNotEqual(response.status_code, 403)

    def test_hr_dostaje_403(self):
        self.client.force_login(self.hr)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)

    def test_kierownik_dostaje_403(self):
        self.client.force_login(self.kierownik)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)

    def test_niezalogowany_dostaje_redirect(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response['Location'])


class UsunPracownikaAccessTest(TestCase):
    """usun_pracownika: tylko admin może usuwać pojedynczego pracownika."""

    def setUp(self):
        self.client = Client()
        from apps.pracownicy.models import Pracownik
        self.pracownik = Pracownik.objects.create(imie='Jan', nazwisko='Testowy')
        self.url = reverse('pracownicy:usun_pracownika', args=[self.pracownik.pk])
        self.admin = _make_user('admin_p', 'admin')
        self.hr = _make_user('hr_p', 'hr')
        self.kierownik = _make_user('kierownik_p', 'kierownik')

    def test_hr_dostaje_403(self):
        self.client.force_login(self.hr)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)

    def test_kierownik_dostaje_403(self):
        self.client.force_login(self.kierownik)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)

    def test_admin_moze_usunac(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url)
        self.assertNotEqual(response.status_code, 403)


class UsunPlanAccessTest(TestCase):
    """usun_plan: tylko admin może usuwać plan dzienny."""

    def setUp(self):
        self.client = Client()
        from apps.pracownicy.models import PlanDzienny
        self.plan = PlanDzienny.objects.create(nazwa_pliku='test.xlsx')
        self.url = reverse('pracownicy:usun_plan', args=[self.plan.pk])
        self.admin = _make_user('admin_pl', 'admin')
        self.hr = _make_user('hr_pl', 'hr')
        self.kierownik = _make_user('kierownik_pl', 'kierownik')

    def test_hr_dostaje_403(self):
        self.client.force_login(self.hr)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)

    def test_kierownik_dostaje_403(self):
        self.client.force_login(self.kierownik)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)

    def test_admin_moze_usunac(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url)
        self.assertNotEqual(response.status_code, 403)
