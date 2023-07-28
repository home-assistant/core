"""Test the weather websocket API."""
from homeassistant.components.weather import WeatherEntityFeature
from homeassistant.components.weather.const import DOMAIN
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import create_entity

from tests.typing import WebSocketGenerator


async def test_device_class_units(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test we can get supported units."""
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": "weather/convertible_units",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "units": {
            "precipitation_unit": ["in", "mm"],
            "pressure_unit": ["hPa", "inHg", "mbar", "mmHg"],
            "temperature_unit": ["°C", "°F"],
            "visibility_unit": ["km", "mi"],
            "wind_speed_unit": ["ft/s", "km/h", "kn", "m/s", "mph"],
        }
    }


async def test_subscribe_forecast(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    enable_custom_integrations: None,
) -> None:
    """Test multiple forecast."""

    entity0 = await create_entity(
        hass,
        native_temperature=38,
        native_temperature_unit=UnitOfTemperature.CELSIUS,
        supported_features=WeatherEntityFeature.FORECAST_DAILY,
    )

    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "weather/subscribe_forecast",
            "forecast_type": "daily",
            "entity_id": entity0.entity_id,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None
    subscription_id = msg["id"]

    msg = await client.receive_json()
    assert msg["id"] == subscription_id
    assert msg["type"] == "event"
    forecast = msg["event"]
    assert forecast == {
        "type": "daily",
        "forecast": [
            {
                "cloud_coverage": None,
                "temperature": 38.0,
                "templow": 38.0,
                "uv_index": None,
                "wind_bearing": None,
            }
        ],
    }

    await entity0.async_update_listeners(None)
    msg = await client.receive_json()
    assert msg["event"] == forecast

    await entity0.async_update_listeners(["daily"])
    msg = await client.receive_json()
    assert msg["event"] == forecast

    entity0.forecast_list = None
    await entity0.async_update_listeners(None)
    msg = await client.receive_json()
    assert msg["event"] == {"type": "daily", "forecast": None}


async def test_subscribe_forecast_unknown_entity(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    enable_custom_integrations: None,
) -> None:
    """Test multiple forecast."""

    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "weather/subscribe_forecast",
            "forecast_type": "daily",
            "entity_id": "weather.unknown",
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"] == {
        "code": "invalid_entity_id",
        "message": "Weather entity not found: weather.unknown",
    }


async def test_subscribe_forecast_unsupported(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    enable_custom_integrations: None,
) -> None:
    """Test multiple forecast."""

    entity0 = await create_entity(
        hass,
        native_temperature=38,
        native_temperature_unit=UnitOfTemperature.CELSIUS,
    )

    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "weather/subscribe_forecast",
            "forecast_type": "daily",
            "entity_id": entity0.entity_id,
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"] == {
        "code": "forecast_not_supported",
        "message": "The weather entity does not support forecast type: daily",
    }
