"""Test the hardware websocket API."""
from homeassistant.components.hardware.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_board_info(hass: HomeAssistant, hass_ws_client) -> None:
    """Test we can get the board info."""
    assert await async_setup_component(hass, DOMAIN, {})

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "hardware/info"})
    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["success"]
    assert msg["result"] == {"hardware": []}
