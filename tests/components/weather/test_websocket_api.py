"""Test the weather websocket API."""
from pytest_unordered import unordered

from homeassistant.components.weather.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_device_class_units(hass: HomeAssistant, hass_ws_client) -> None:
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
            "precipitation_unit": unordered(["mm", "in"]),
            "pressure_unit": unordered(["mbar", "mmHg", "inHg", "hPa"]),
            "temperature_unit": unordered(["°F", "°C"]),
            "visibility_unit": unordered(["km", "mi"]),
            "wind_speed_unit": unordered(["mph", "km/h", "kn", "m/s", "ft/s"]),
        }
    }
