"""Common methods used across tests for Bond."""
from asyncio import TimeoutError as AsyncIOTimeoutError
from contextlib import nullcontext
from datetime import timedelta
from typing import Any, Dict, Optional

from homeassistant import core
from homeassistant.components.bond.const import DOMAIN as BOND_DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, STATE_UNAVAILABLE
from homeassistant.setup import async_setup_component
from homeassistant.util import utcnow

from tests.async_mock import patch
from tests.common import MockConfigEntry, async_fire_time_changed


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
):
    """Set up Bond entity."""
    config_entry.add_to_hass(hass)

    with patch_bond_version(enabled=patch_version), patch_bond_device_ids(
        enabled=patch_device_ids
    ), patch_setup_entry("cover", enabled=patch_platforms), patch_setup_entry(
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
    discovered_device: Dict[str, Any],
    bond_device_id: str = "bond-device-id",
    props: Dict[str, Any] = None,
    bond_version: Dict[str, Any] = None,
):
    """Set up the specified Bond platform."""
    mock_entry = MockConfigEntry(
        domain=BOND_DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_ACCESS_TOKEN: "test-token"},
    )
    mock_entry.add_to_hass(hass)

    with patch("homeassistant.components.bond.PLATFORMS", [platform]):
        with patch_bond_version(return_value=bond_version), patch_bond_device_ids(
            return_value=[bond_device_id]
        ), patch_bond_device(
            return_value=discovered_device
        ), patch_bond_device_state(), patch_bond_device_properties(
            return_value=props
        ), patch_bond_device_state():
            assert await async_setup_component(hass, BOND_DOMAIN, {})
            await hass.async_block_till_done()

    return mock_entry


def patch_bond_version(
    enabled: bool = True, return_value: Optional[dict] = None, side_effect=None
):
    """Patch Bond API version endpoint."""
    if not enabled:
        return nullcontext()

    if return_value is None:
        return_value = {"bondid": "test-bond-id"}

    return patch(
        "homeassistant.components.bond.Bond.version",
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
        "homeassistant.components.bond.Bond.device", return_value=return_value,
    )


def patch_bond_action():
    """Patch Bond API action endpoint."""
    return patch("homeassistant.components.bond.Bond.action")


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
    hass: core.HomeAssistant, domain: str, device: Dict[str, Any], entity_id: str
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
