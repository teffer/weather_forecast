from django.test import TestCase, Client
from django.urls import reverse
import json
from .models import CitySearchCount
from .views import decode_wmo_code

class WeatherAppTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.index_url = reverse('index')
        self.search_counts_url = reverse('get_search_counts')
        self.get_cities_url = reverse('get_cities')
        self.city_name = "Лондон"
        self.invalid_city_name = "123йувфв"
        
    def test_index_view_with_invalid_city(self):
        response = self.client.post(self.index_url, {'city': self.invalid_city_name})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '123йувфв')

    def test_get_search_counts_for_existing_city(self):
        CitySearchCount.objects.create(city=self.city_name, search_count=5)
        response = self.client.get(f"{self.search_counts_url}?city={self.city_name}")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data[0]['city'], self.city_name)
        self.assertEqual(data[0]['search_count'], 5)

    def test_get_search_counts_for_non_existing_city(self):
        response = self.client.get(f"{self.search_counts_url}?city={self.invalid_city_name}")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data, [])

    def test_decode_wmo_code(self):
        self.assertEqual(decode_wmo_code(0), "Ясно")
        self.assertEqual(decode_wmo_code(99), "Гроза с градом")
        self.assertEqual(decode_wmo_code(999), "неизвестный код")