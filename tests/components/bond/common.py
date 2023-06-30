"""Common methods used across tests for Bond."""
from __future__ import annotations

from asyncio import TimeoutError as AsyncIOTimeoutError
from contextlib import nullcontext
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from aiohttp.client_exceptions import ClientResponseError
from bond_async import DeviceType

from homeassistant import core
from homeassistant.components.bond.const import DOMAIN as BOND_DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, STATE_UNAVAILABLE
from homeassistant.setup import async_setup_component
from homeassistant.util import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed


async def remove_device(ws_client, device_id, config_entry_id):
    """Remove config entry from a device."""
    await ws_client.send_json(
        {
            "id": 5,
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": config_entry_id,
            "device_id": device_id,
        }
    )
    response = await ws_client.receive_json()
    return response["success"]


def ceiling_fan_with_breeze(name: str):
    """Create a ceiling fan with given name with breeze support."""
    return {
        "name": name,
        "type": DeviceType.CEILING_FAN,
        "actions": ["SetSpeed", "SetDirection", "BreezeOn"],
    }


def patch_setup_entry(domain: str, *, enabled: bool = True):
    """Patch async_setup_entry for specified domain."""
    if not enabled:
        return nullcontext()

    return patch(f"homeassistant.components.bond.{domain}.async_setup_entry")


async def setup_bond_entity(
    hass: core.HomeAssistant,
    config_entry: MockConfigEntry,
    *,
    patch_version=False,
    patch_device_ids=False,
    patch_platforms=False,
    patch_bridge=False,
    patch_token=False,
):
    """Set up Bond entity."""
    config_entry.add_to_hass(hass)

    with patch_start_bpup(), patch_bond_bridge(enabled=patch_bridge), patch_bond_token(
        enabled=patch_token
    ), patch_bond_version(enabled=patch_version), patch_bond_device_ids(
        enabled=patch_device_ids
    ), patch_setup_entry(
        "cover", enabled=patch_platforms
    ), patch_setup_entry(
        "fan", enabled=patch_platforms
    ), patch_setup_entry(
        "light", enabled=patch_platforms
    ), patch_setup_entry(
        "switch", enabled=patch_platforms
    ):
        return await hass.config_entries.async_setup(config_entry.entry_id)


async def setup_platform(
    hass: core.HomeAssistant,
    platform: str,
    discovered_device: dict[str, Any],
    *,
    bond_device_id: str = "bond-device-id",
    bond_version: dict[str, Any] = None,
    props: dict[str, Any] = None,
    state: dict[str, Any] = None,
    bridge: dict[str, Any] = None,
    token: dict[str, Any] = None,
):
    """Set up the specified Bond platform."""
    mock_entry = MockConfigEntry(
        domain=BOND_DOMAIN,
        data={CONF_HOST: "some host", CONF_ACCESS_TOKEN: "test-token"},
    )
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.bond.PLATFORMS", [platform]
    ), patch_bond_version(return_value=bond_version), patch_bond_bridge(
        return_value=bridge
    ), patch_bond_token(
        return_value=token
    ), patch_bond_device_ids(
        return_value=[bond_device_id]
    ), patch_start_bpup(), patch_bond_device(
        return_value=discovered_device
    ), patch_bond_device_properties(
        return_value=props
    ), patch_bond_device_state(
        return_value=state
    ):
        assert await async_setup_component(hass, BOND_DOMAIN, {})
        await hass.async_block_till_done()

    return mock_entry


def patch_bond_version(
    enabled: bool = True, return_value: dict | None = None, side_effect=None
):
    """Patch Bond API version endpoint."""
    if not enabled:
        return nullcontext()

    if return_value is None:
        return_value = {
            "bondid": "ZXXX12345",
            "target": "test-model",
            "fw_ver": "test-version",
            "mcu_ver": "test-hw-version",
        }

    return patch(
        "homeassistant.components.bond.Bond.version",
        return_value=return_value,
        side_effect=side_effect,
    )


def patch_bond_bridge(
    enabled: bool = True, return_value: dict | None = None, side_effect=None
):
    """Patch Bond API bridge endpoint."""
    if not enabled:
        return nullcontext()

    if return_value is None:
        return_value = {
            "name": "bond-name",
            "location": "bond-location",
            "bluelight": 127,
        }

    return patch(
        "homeassistant.components.bond.Bond.bridge",
        return_value=return_value,
        side_effect=side_effect,
    )


def patch_bond_token(
    enabled: bool = True, return_value: dict | None = None, side_effect=None
):
    """Patch Bond API token endpoint."""
    if not enabled:
        return nullcontext()

    if return_value is None:
        return_value = {"locked": 1}

    return patch(
        "homeassistant.components.bond.Bond.token",
        return_value=return_value,
        side_effect=side_effect,
    )


def patch_bond_device_ids(enabled: bool = True, return_value=None, side_effect=None):
    """Patch Bond API devices endpoint."""
    if not enabled:
        return nullcontext()

    if return_value is None:
        return_value = []

    return patch(
        "homeassistant.components.bond.Bond.devices",
        return_value=return_value,
        side_effect=side_effect,
    )


def patch_bond_device(return_value=None):
    """Patch Bond API device endpoint."""
    return patch(
        "homeassistant.components.bond.Bond.device",
        return_value=return_value,
    )


def patch_start_bpup():
    """Patch start_bpup."""
    return patch(
        "homeassistant.components.bond.start_bpup",
        return_value=MagicMock(),
    )


def patch_bond_action():
    """Patch Bond API action endpoint."""
    return patch("homeassistant.components.bond.Bond.action")


def patch_bond_action_returns_clientresponseerror():
    """Patch Bond API action endpoint to throw ClientResponseError."""
    return patch(
        "homeassistant.components.bond.Bond.action",
        side_effect=ClientResponseError(
            request_info=None, history=None, code=405, message="Method Not Allowed"
        ),
    )


def patch_bond_device_properties(return_value=None):
    """Patch Bond API device properties endpoint."""
    if return_value is None:
        return_value = {}

    return patch(
        "homeassistant.components.bond.Bond.device_properties",
        return_value=return_value,
    )


def patch_bond_device_state(return_value=None, side_effect=None):
    """Patch Bond API device state endpoint."""
    if return_value is None:
        return_value = {}

    return patch(
        "homeassistant.components.bond.Bond.device_state",
        return_value=return_value,
        side_effect=side_effect,
    )


async def help_test_entity_available(
    hass: core.HomeAssistant, domain: str, device: dict[str, Any], entity_id: str
):
    """Run common test to verify available property."""
    await setup_platform(hass, domain, device)

    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    with patch_bond_device_state(side_effect=AsyncIOTimeoutError()):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    with patch_bond_device_state(return_value={}):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE


def ceiling_fan(name: str):
    """Create a ceiling fan with given name."""
    return {
        "name": name,
        "type": DeviceType.CEILING_FAN,
        "actions": ["SetSpeed", "SetDirection"],
    }
