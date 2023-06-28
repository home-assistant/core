"""Test the sensor websocket API."""
from homeassistant.components.sensor.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import WebSocketGenerator


async def test_device_class_units(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test we can get supported units."""
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    # Device class with units which sensor allows customizing & converting
    await client.send_json_auto_id(
        {
            "type": "sensor/device_class_convertible_units",
            "device_class": "speed",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "units": ["ft/s", "in/d", "in/h", "km/h", "kn", "m/s", "mm/d", "mm/h", "mph"]
    }

    # Device class with units which include `None`
    await client.send_json_auto_id(
        {
            "type": "sensor/device_class_convertible_units",
            "device_class": "power_factor",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"units": ["%", None]}

    # Device class with units which sensor doesn't allow customizing & converting
    await client.send_json_auto_id(
        {
            "type": "sensor/device_class_convertible_units",
            "device_class": "pm1",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"units": []}

    # Unknown device class
    await client.send_json_auto_id(
        {
            "type": "sensor/device_class_convertible_units",
            "device_class": "kebabsås",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"units": []}
