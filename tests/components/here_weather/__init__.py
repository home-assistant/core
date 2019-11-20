"""Tests for here_weather component."""
import urllib

PLATFORM = "here_weather"

APP_ID = "test"
APP_CODE = "test"

ZIP_CODE = "10025"

LOCATION_NAME = "New York"

LATITUDE = "40.79962"
LONGITUDE = "-73.970314"


def build_base_mock_url(app_id, app_code, additional_params):
    """Construct a url for HERE."""
    base_url = "https://weather.api.here.com/weather/1.0/report.json?"
    parameters = {
        "app_id": app_id,
        "app_code": app_code,
        "oneobservation": True,
        "metric": True,
    }
    parameters.update(additional_params)
    url = base_url + urllib.parse.urlencode(parameters)
    return url


def build_zip_code_imperial_mock_url(app_id, app_code, zip_code, product):
    """Construct a url for HERE."""
    parameters = {"product": product, "zipcode": zip_code, "metric": False}
    url = build_base_mock_url(app_id, app_code, parameters)
    return url


def build_coordinates_mock_url(app_id, app_code, latitude, longitude, product):
    """Construct a url for HERE."""
    parameters = {"product": product, "latitude": latitude, "longitude": longitude}
    url = build_base_mock_url(app_id, app_code, parameters)
    return url


def build_location_name_mock_url(app_id, app_code, location_name, product):
    """Construct a url for HERE."""
    parameters = {"product": product, "name": location_name}
    url = build_base_mock_url(app_id, app_code, parameters)
    return url


def build_zip_code_mock_url(app_id, app_code, zip_code, product):
    """Construct a url for HERE."""
    parameters = {"product": product, "zipcode": zip_code}
    url = build_base_mock_url(app_id, app_code, parameters)
    return url
