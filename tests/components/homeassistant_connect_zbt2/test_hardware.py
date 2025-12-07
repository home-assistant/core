"""Test the Home Assistant Connect ZBT-2 hardware platform."""

from homeassistant.components.homeassistant_connect_zbt2.const import DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator

CONFIG_ENTRY_DATA = {
    "device": "/dev/serial/by-id/usb-Nabu_Casa_ZBT-2_80B54EEFAE18-if01-port0",
    "vid": "303A",
    "pid": "4001",
    "serial_number": "80B54EEFAE18",
    "manufacturer": "Nabu Casa",
    "product": "ZBT-2",
    "firmware": "ezsp",
    "firmware_version": "7.4.4.0 build 0",
}


async def test_hardware_info(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, addon_store_info
) -> None:
    """Test we can get the board info."""
    assert await async_setup_component(hass, "usb", {})
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)

    # Setup the config entry
    config_entry = MockConfigEntry(
        data=CONFIG_ENTRY_DATA,
        domain=DOMAIN,
        options={},
        title="Home Assistant Connect ZBT-2",
        unique_id="unique_1",
        version=1,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "hardware/info"})
    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["success"]
    assert msg["result"] == {
        "hardware": [
            {
                "board": None,
                "config_entries": [config_entry.entry_id],
                "dongle": {
                    "vid": "303A",
                    "pid": "4001",
                    "serial_number": "80B54EEFAE18",
                    "manufacturer": "Nabu Casa",
                    "description": "ZBT-2",
                },
                "name": "Home Assistant Connect ZBT-2",
                "url": "https://support.nabucasa.com/hc/en-us/categories/24734620813469-Home-Assistant-Connect-ZBT-1",
            }
        ]
    }
