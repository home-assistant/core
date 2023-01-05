"""Test the sensor websocket API."""
from pytest_unordered import unordered

from homeassistant.components.sensor.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_device_class_units(hass: HomeAssistant, hass_ws_client) -> None:
    """Test we can get supported units."""
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    await client.send_json(
        {"id": 1, "type": "sensor/device_class_units", "device_class": "energy"}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"units": unordered(["Wh", "GJ", "kWh", "MWh"])}

    await client.send_json(
        {"id": 2, "type": "sensor/device_class_units", "device_class": "kebabsås"}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"units": unordered([])}
