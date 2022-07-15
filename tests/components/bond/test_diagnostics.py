"""Test bond diagnostics."""

from homeassistant.components.fan import DOMAIN as FAN_DOMAIN

from .common import ceiling_fan_with_breeze, setup_platform

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_diagnostics(hass, hass_client):
    """Test generating diagnostics for a config entry."""

    entry = await setup_platform(
        hass,
        FAN_DOMAIN,
        ceiling_fan_with_breeze("name-1"),
        bond_device_id="test-device-id",
        props={"max_speed": 6},
    )
    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    mock_device = diag["devices"][0]
    mock_device["attrs"]["actions"] = set(mock_device["attrs"]["actions"])
    mock_device["supported_actions"] = set(mock_device["supported_actions"])

    assert diag == {
        "devices": [
            {
                "attrs": {
                    "actions": {"SetSpeed", "SetDirection", "BreezeOn"},
                    "name": "name-1",
                    "type": "CF",
                },
                "device_id": "test-device-id",
                "props": {"max_speed": 6},
                "supported_actions": {"BreezeOn", "SetSpeed", "SetDirection"},
            }
        ],
        "entry": {
            "data": {"access_token": "**REDACTED**", "host": "some host"},
            "title": "Mock Title",
        },
        "hub": {"version": {"bondid": "ZXXX12345"}},
    }
