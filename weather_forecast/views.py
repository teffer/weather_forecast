from django.shortcuts import render
import requests
import openmeteo_requests
import requests_cache
import pandas as pd
from retry_requests import retry
from geopy.geocoders import Nominatim

API_URL = "https://api.open-meteo.com/v1/forecast"

def index(request):
    weather_data = None
    if request.method == "POST":
        city = request.POST.get("city")
        if city:
            weather_data = get_weather(city)
    return render(request, 'index.html', {'weather': weather_data})

def get_weather(city):
    # Вычисление широты и долготы города
    geo = Nominatim(user_agent='studyagentLemberg')
    code = geo.geocode('Berlin')
    latitude = code.latitude
    longitude = code.longitude
    cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
    retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
    openmeteo = openmeteo_requests.Client(session = retry_session)

    # Make sure all required weather variables are listed here
    # The order of variables in hourly or daily is important to assign them correctly below
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m,wind_speed_10m"
    }
    responses = openmeteo.weather_api(url, params=params)

    # Process first location. Add a for-loop for multiple locations or weather models
    response = responses[0]
    print(f"Coordinates {response.Latitude()}°N {response.Longitude()}°E")
    print(f"Elevation {response.Elevation()} m asl")
    print(f"Timezone {response.Timezone()} {response.TimezoneAbbreviation()}")
    print(f"Timezone difference to GMT+0 {response.UtcOffsetSeconds()} s")

    # Process hourly data. The order of variables needs to be the same as requested.
    hourly = response.Hourly()
    hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()

    hourly_data = {"date": pd.date_range(
        start = pd.to_datetime(hourly.Time(), unit = "s", utc = True),
        end = pd.to_datetime(hourly.TimeEnd(), unit = "s", utc = True),
        freq = pd.Timedelta(seconds = hourly.Interval()),
        inclusive = "left"
    )}
    hourly_data["temperature_2m"] = hourly_temperature_2m
    hourly_dataframe = pd.DataFrame(data = hourly_data)
    hourly_dataframe['hour'] = hourly_dataframe['date'].dt.hour
    hourly_dataframe['day'] = hourly_dataframe['date'].dt.date
    day_temperature = hourly_dataframe[hourly_dataframe['hour'] == 12].set_index('day')['temperature_2m']
    night_temperature = hourly_dataframe[hourly_dataframe['hour'] == 0].set_index('day')['temperature_2m']

    weather_data = {
        "city": city,
        "data": [
            {
                "date": day.strftime('%d %B').capitalize(),
                "temperature_day": round(day_temperature[day]),
                "temperature_night": round(night_temperature[day])
            }
            for day in day_temperature.index
        ]
    }
    return weather_data