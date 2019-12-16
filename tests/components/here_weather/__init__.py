"""Tests for here_weather component."""
import urllib

PLATFORM = "here_weather"

API_KEY = "test"

ZIP_CODE = "10025"

LOCATION_NAME = "New York"

LATITUDE = "40.79962"
LONGITUDE = "-73.970314"


def build_base_mock_url(api_key, additional_params):
    """Construct a url for HERE."""
    base_url = "https://weather.api.here.com/weather/1.0/report.json?"
    parameters = {
        "apikey": api_key,
        "oneobservation": True,
        "metric": True,
    }
    parameters.update(additional_params)
    url = base_url + urllib.parse.urlencode(parameters)
    return url


def build_zip_code_imperial_mock_url(api_key, zip_code, product):
    """Construct a url for HERE."""
    parameters = {"product": product, "zipcode": zip_code, "metric": False}
    url = build_base_mock_url(api_key, parameters)
    return url


def build_coordinates_mock_url(api_key, latitude, longitude, product):
    """Construct a url for HERE."""
    parameters = {"product": product, "latitude": latitude, "longitude": longitude}
    url = build_base_mock_url(api_key, parameters)
    return url


def build_location_name_mock_url(api_key, location_name, product):
    """Construct a url for HERE."""
    parameters = {"product": product, "name": location_name}
    url = build_base_mock_url(api_key, parameters)
    return url


def build_zip_code_mock_url(api_key, zip_code, product):
    """Construct a url for HERE."""
    parameters = {"product": product, "zipcode": zip_code}
    url = build_base_mock_url(api_key, parameters)
    return url
