"""Test the sensor websocket API."""
from pytest_unordered import unordered

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
    await client.send_json(
        {
            "id": 1,
            "type": "sensor/device_class_convertible_units",
            "device_class": "speed",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "units": unordered(
            ["km/h", "kn", "mph", "in/h", "in/d", "ft/s", "mm/d", "mm/h", "m/s"]
        )
    }

    # Device class with units which sensor doesn't allow customizing & converting
    await client.send_json(
        {
            "id": 2,
            "type": "sensor/device_class_convertible_units",
            "device_class": "pm1",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"units": []}

    # Unknown device class
    await client.send_json(
        {
            "id": 3,
            "type": "sensor/device_class_convertible_units",
            "device_class": "kebabsås",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"units": unordered([])}
