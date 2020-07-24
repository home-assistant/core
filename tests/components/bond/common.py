"""Common methods used across tests for Bond."""
from asyncio import TimeoutError as AsyncIOTimeoutError
from datetime import timedelta
from typing import Any, Dict

from homeassistant import core
from homeassistant.components.bond.const import DOMAIN as BOND_DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, STATE_UNAVAILABLE
from homeassistant.setup import async_setup_component
from homeassistant.util import utcnow

from tests.async_mock import patch
from tests.common import MockConfigEntry, async_fire_time_changed

MOCK_HUB_VERSION: dict = {"bondid": "test-bond-id"}


async def setup_bond_entity(
    hass: core.HomeAssistant, config_entry: MockConfigEntry, hub_version=None
):
    """Set up Bond entity."""
    if hub_version is None:
        hub_version = MOCK_HUB_VERSION

    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.bond.Bond.version", return_value=hub_version):
        return await hass.config_entries.async_setup(config_entry.entry_id)


async def setup_platform(
    hass: core.HomeAssistant,
    platform: str,
    discovered_device: Dict[str, Any],
    bond_device_id: str = "bond-device-id",
    props: Dict[str, Any] = None,
):
    """Set up the specified Bond platform."""
    if not props:
        props = {}

    mock_entry = MockConfigEntry(
        domain=BOND_DOMAIN,
        data={CONF_HOST: "1.1.1.1", CONF_ACCESS_TOKEN: "test-token"},
    )
    mock_entry.add_to_hass(hass)

    with patch("homeassistant.components.bond.PLATFORMS", [platform]), patch(
        "homeassistant.components.bond.Bond.version", return_value=MOCK_HUB_VERSION
    ), patch_bond_device_ids(return_value=[bond_device_id],), patch(
        "homeassistant.components.bond.Bond.device", return_value=discovered_device
    ), patch_bond_device_state(
        return_value={}
    ), patch(
        "homeassistant.components.bond.Bond.device_properties", return_value=props
    ), patch(
        "homeassistant.components.bond.Bond.device_state", return_value={}
    ):
        assert await async_setup_component(hass, BOND_DOMAIN, {})
        await hass.async_block_till_done()

    return mock_entry


def patch_bond_device_ids(return_value=None):
    """Patch Bond API devices command."""
    if return_value is None:
        return_value = []

    return patch(
        "homeassistant.components.bond.Bond.devices", return_value=return_value,
    )


def patch_bond_action():
    """Patch Bond API action command."""
    return patch("homeassistant.components.bond.Bond.action")


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
