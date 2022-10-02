"""Test the Lutron Caseta diagnostics."""

from unittest.mock import patch

from homeassistant.components.lutron_caseta import DOMAIN
from homeassistant.components.lutron_caseta.const import (
    CONF_CA_CERTS,
    CONF_CERTFILE,
    CONF_KEYFILE,
)
from homeassistant.const import CONF_HOST

from . import MockBridge

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_diagnostics(hass, hass_client) -> None:
    """Test generating diagnostics for lutron_caseta."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_KEYFILE: "",
            CONF_CERTFILE: "",
            CONF_CA_CERTS: "",
        },
        unique_id="abc",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.lutron_caseta.Smartbridge.create_tls",
        return_value=MockBridge(can_connect=True),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert diag == {
        "data": {
            "areas": {},
            "buttons": {},
            "devices": {
                "1": {
                    "model": "model",
                    "name": "bridge",
                    "serial": 1234,
                    "type": "type",
                },
                "801": {
                    "device_id": "801",
                    "current_state": 100,
                    "fan_speed": None,
                    "zone": "801",
                    "name": "Basement Bedroom_Main Lights",
                    "button_groups": None,
                    "type": "Dimmed",
                    "model": None,
                    "serial": None,
                    "tilt": None,
                },
                "802": {
                    "device_id": "802",
                    "current_state": 100,
                    "fan_speed": None,
                    "zone": "802",
                    "name": "Basement Bedroom_Left Shade",
                    "button_groups": None,
                    "type": "SerenaRollerShade",
                    "model": None,
                    "serial": None,
                    "tilt": None,
                },
                "803": {
                    "device_id": "803",
                    "current_state": 100,
                    "fan_speed": None,
                    "zone": "803",
                    "name": "Basement Bathroom_Exhaust Fan",
                    "button_groups": None,
                    "type": "Switched",
                    "model": None,
                    "serial": None,
                    "tilt": None,
                },
                "804": {
                    "device_id": "804",
                    "current_state": 100,
                    "fan_speed": None,
                    "zone": "804",
                    "name": "Master Bedroom_Ceiling Fan",
                    "button_groups": None,
                    "type": "FanSpeed",
                    "model": None,
                    "serial": None,
                    "tilt": None,
                },
                "901": {
                    "device_id": "901",
                    "current_state": 100,
                    "fan_speed": None,
                    "zone": "901",
                    "name": "Kitchen_Main Lights",
                    "button_groups": None,
                    "type": "WallDimmer",
                    "model": None,
                    "serial": 5442321,
                    "tilt": None,
                },
            },
            "occupancy_groups": {},
            "scenes": {},
        },
        "entry": {
            "data": {"ca_certs": "", "certfile": "", "host": "1.1.1.1", "keyfile": ""},
            "title": "Mock Title",
        },
    }
