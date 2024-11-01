"""Test the number websocket API."""

from homeassistant.components.number.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import WebSocketGenerator


async def test_device_class_units(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test we can get supported units."""
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    # Device class with units which number allows customizing & converting
    await client.send_json_auto_id(
        {
            "type": "number/device_class_convertible_units",
            "device_class": "temperature",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"units": ["K", "°C", "°F"]}

    # Device class with units which number doesn't allow customizing & converting
    await client.send_json_auto_id(
        {
            "type": "number/device_class_convertible_units",
            "device_class": "energy",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"units": []}

    # Unknown device class
    await client.send_json_auto_id(
        {
            "type": "number/device_class_convertible_units",
            "device_class": "kebabsås",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"units": []}
