"""Test bond diagnostics."""

from bond_async import Action, DeviceType

from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.core import HomeAssistant

from .common import ceiling_fan_with_breeze, setup_group_platform, setup_platform

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


def fan_group(name: str) -> dict[str, list[str] | str]:
    """Create a ceiling fan group."""
    return {
        "name": name,
        "types": [DeviceType.CEILING_FAN],
        "locations": ["Den"],
        "actions": [
            Action.TURN_ON,
            Action.TURN_OFF,
            Action.SET_SPEED,
            Action.SET_DIRECTION,
        ],
    }


async def test_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
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
        "groups": [],
        "hub": {
            "version": {
                "bondid": "ZXXX12345",
                "fw_ver": "test-version",
                "mcu_ver": "test-hw-version",
                "target": "test-model",
            }
        },
    }


async def test_group_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test generating diagnostics for a Bond group."""
    entry = await setup_group_platform(
        hass,
        FAN_DOMAIN,
        fan_group("name-1"),
        bond_group_id="test-group-id",
        props={"max_speed": 6},
    )

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    mock_group = diag["groups"][0]
    mock_group["attrs"]["actions"] = set(mock_group["attrs"]["actions"])
    mock_group["supported_actions"] = set(mock_group["supported_actions"])

    assert diag == {
        "devices": [],
        "entry": {
            "data": {"access_token": "**REDACTED**", "host": "some host"},
            "title": "Mock Title",
        },
        "groups": [
            {
                "attrs": {
                    "actions": {"TurnOn", "TurnOff", "SetSpeed", "SetDirection"},
                    "locations": ["Den"],
                    "name": "name-1",
                    "types": ["CF"],
                },
                "group_id": "test-group-id",
                "props": {"max_speed": 6},
                "supported_actions": {
                    "SetDirection",
                    "SetSpeed",
                    "TurnOff",
                    "TurnOn",
                },
            }
        ],
        "hub": {
            "version": {
                "bondid": "ZXXX12345",
                "fw_ver": "test-version",
                "mcu_ver": "test-hw-version",
                "target": "test-model",
            }
        },
    }
