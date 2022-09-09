"""Test the Home Assistant Sky Connect hardware platform."""
from unittest.mock import patch

from homeassistant.components.homeassistant_sky_connect.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CONFIG_ENTRY_DATA = {
    "device": "bla_device",
    "vid": "bla_vid",
    "pid": "bla_pid",
    "serial_number": "bla_serial_number",
    "manufacturer": "bla_manufacturer",
    "description": "bla_description",
}

CONFIG_ENTRY_DATA_2 = {
    "device": "bla_device_2",
    "vid": "bla_vid_2",
    "pid": "bla_pid_2",
    "serial_number": "bla_serial_number_2",
    "manufacturer": "bla_manufacturer_2",
    "description": "bla_description_2",
}


async def test_hardware_info(hass: HomeAssistant, hass_ws_client) -> None:
    """Test we can get the board info."""
    # Setup the config entry
    config_entry = MockConfigEntry(
        data=CONFIG_ENTRY_DATA,
        domain=DOMAIN,
        options={},
        title="Home Assistant Sky Connect",
        unique_id="unique_1",
    )
    config_entry.add_to_hass(hass)
    config_entry_2 = MockConfigEntry(
        data=CONFIG_ENTRY_DATA_2,
        domain=DOMAIN,
        options={},
        title="Home Assistant Sky Connect",
        unique_id="unique_2",
    )
    config_entry_2.add_to_hass(hass)
    with patch(
        "homeassistant.components.homeassistant_sky_connect.usb.async_is_plugged_in",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    await client.send_json({"id": 1, "type": "hardware/info"})
    msg = await client.receive_json()

    assert msg["id"] == 1
    assert msg["success"]
    assert msg["result"] == {
        "hardware": [
            {
                "board": None,
                "dongle": {
                    "vid": "bla_vid",
                    "pid": "bla_pid",
                    "serial_number": "bla_serial_number",
                    "manufacturer": "bla_manufacturer",
                    "description": "bla_description",
                },
                "name": "Home Assistant Sky Connect",
                "url": None,
            },
            {
                "board": None,
                "dongle": {
                    "vid": "bla_vid_2",
                    "pid": "bla_pid_2",
                    "serial_number": "bla_serial_number_2",
                    "manufacturer": "bla_manufacturer_2",
                    "description": "bla_description_2",
                },
                "name": "Home Assistant Sky Connect",
                "url": None,
            },
        ]
    }
