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
        self.client.login(username='admin_test', password='testpass123')
        response = self.client.post(self.url)
        # Redirect po usunięciu — nie 403
        self.assertNotEqual(response.status_code, 403)

    def test_hr_dostaje_403(self):
        self.client.login(username='hr_test', password='testpass123')
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)

    def test_kierownik_dostaje_403(self):
        self.client.login(username='kierownik_test', password='testpass123')
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 403)

    def test_niezalogowany_dostaje_redirect(self):
        response = self.client.post(self.url)
        # Niezalogowany → redirect na login, nie 403
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response['Location'])
