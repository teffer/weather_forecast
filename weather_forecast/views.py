import requests
import openmeteo_requests
import requests_cache
import os, json
import pandas as pd
from django.shortcuts import render
from retry_requests import retry
from geopy.geocoders import Nominatim
from googletrans import Translator
from django.http import JsonResponse
from django.conf import settings
from urllib.parse import quote, unquote
from .models import CitySearchCount
from django.views.decorators.csrf import csrf_exempt

API_URL = "https://api.open-meteo.com/v1/forecast"

WMO_LIST = {
    0: "Ясно",
    1: "Преимущественно ясно",
    2: "Переменная облачность",
    3: "Пасмурно",
    45: "Туман",
    48: "Изморозь",
    51: "Легкий моросящий дождь",
    53: "Умеренный моросящий дождь",
    55: "Сильный моросящий дождь",
    56: "Легкий моросящий дождь",
    57: "Сильный моросящий дождь",
    61: "Слабый дождь",
    63: "Умеренный дождь",
    65: "Сильный дождь",
    66: "Слабый дождь с градом",
    67: "Сильный дождь с градом",
    71: "Слабый снег",
    73: "Умеренный снег",
    75: "Снегопад",
    77: "Снегопад",
    80: "Слабый ливень",
    81: "Умеренный ливень",
    82: "Сильный ливень",
    85: "Снегопад",
    86: "Снегопад",
    95: "Гроза",
    96: "Гроза с градом",
    99: "Гроза с градом"
}
@csrf_exempt
def index(request):
    weather_data = None
    last_city = unquote(request.COOKIES.get('last_city', ''))
    if request.method == "POST":
        city = request.POST.get("city")
        if city:
            weather_data = get_weather(city)
            if weather_data is not None:
                city_search, created = CitySearchCount.objects.get_or_create(city=city)
                city_search.search_count += 1
                city_search.save()
                response = render(request, 'index.html', {'weather': weather_data})
                response.set_cookie('last_city', quote(city))   
                return response
            else: 
                return render(request, 'index.html', {'error': city})
    elif last_city:
        weather_data = get_weather(last_city)
        city_search, created = CitySearchCount.objects.get_or_create(city=last_city)
        city_search.search_count += 1
        city_search.save()       
    return render(request, 'index.html', {'weather': weather_data})

def get_weather(city):
    geo = Nominatim(user_agent='studyagentLemberg')
    code = geo.geocode(city)
    if code is not None and code.latitude is not None and code.longitude is not None:
        latitude = code.latitude
        longitude = code.longitude
    else:
        return None
    cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
    retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
    openmeteo = openmeteo_requests.Client(session = retry_session)
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m,weather_code"
    }
    responses = openmeteo.weather_api(API_URL, params=params)
    if responses is None:
        return None
    response = responses[0]
    hourly = response.Hourly()
    hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
    hourly_wmo_code = hourly.Variables(1).ValuesAsNumpy()

    hourly_data = {"date": pd.date_range(
        start = pd.to_datetime(hourly.Time(), unit = "s", utc = True),
        end = pd.to_datetime(hourly.TimeEnd(), unit = "s", utc = True),
        freq = pd.Timedelta(seconds = hourly.Interval()),
        inclusive = "left"
    )}
    hourly_data["temperature_2m"] = hourly_temperature_2m
    hourly_data["code"] = hourly_wmo_code
    hourly_dataframe = pd.DataFrame(data = hourly_data)
    hourly_dataframe['hour'] = hourly_dataframe['date'].dt.hour
    hourly_dataframe['day'] = hourly_dataframe['date'].dt.date
    day_data = hourly_dataframe[hourly_dataframe['hour'] == 12].set_index('day')
    night_data = hourly_dataframe[hourly_dataframe['hour'] == 0].set_index('day')
    day_data['weather_description'] = day_data['code'].apply(decode_wmo_code)
    night_data['weather_description'] = night_data['code'].apply(decode_wmo_code)
    weather_data = {
        "city": city,
        "data": [
            {
                "date": day.strftime('%d %B').capitalize(),
                "temperature_day": round(day_data.loc[day, 'temperature_2m']),
                "temperature_night": round(night_data.loc[day, 'temperature_2m']),
                "weather_day": day_data.loc[day, 'weather_description'],
                "weather_night": night_data.loc[day, 'weather_description']
            }
            for day in day_data.index
        ]
    }
    return weather_data

def get_search_counts(request, city = ''):
    if city == '':
        city_searches = CitySearchCount.objects.all().values('city', 'search_count')
        data = list(city_searches)
    else:
        try:
            city_search = CitySearchCount.objects.get(city=city)
            data = {'city': city_search.city, 'search_count': city_search.search_count}
        except CitySearchCount.DoesNotExist:
            data = {'city': city, 'search_count': 0}
    return JsonResponse(data, safe=False)

def get_cities(request):
    with open("weather_forecast/cities.json", "r", encoding="utf-8") as file:
        cities = json.load(file)
    return JsonResponse(cities)

def decode_wmo_code(code):
    return WMO_LIST.get(code, "неизвестный код")