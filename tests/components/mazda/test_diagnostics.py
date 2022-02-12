"""Test Mazda diagnostics."""

import json

import pytest

from homeassistant.components.mazda.const import DATA_COORDINATOR, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import init_integration

from tests.common import load_fixture
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)


async def test_config_entry_diagnostics(hass: HomeAssistant, hass_client):
    """Test config entry diagnostics."""
    await init_integration(hass)
    assert hass.data[DOMAIN]

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    diagnostics_fixture = json.loads(
        load_fixture("mazda/diagnostics_config_entry.json")
    )

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == diagnostics_fixture
    )


async def test_device_diagnostics(hass: HomeAssistant, hass_client):
    """Test device diagnostics."""
    await init_integration(hass)
    assert hass.data[DOMAIN]

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    device_registry = dr.async_get(hass)
    reg_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "JM000000000000000")},
    )
    assert reg_device is not None

    diagnostics_fixture = json.loads(load_fixture("mazda/diagnostics_device.json"))

    assert (
        await get_diagnostics_for_device(hass, hass_client, config_entry, reg_device)
        == diagnostics_fixture
    )


async def test_device_diagnostics_vehicle_not_found(hass: HomeAssistant, hass_client):
    """Test device diagnostics when the vehicle cannot be found."""
    await init_integration(hass)
    assert hass.data[DOMAIN]

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    device_registry = dr.async_get(hass)
    reg_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "JM000000000000000")},
    )
    assert reg_device is not None

    # Remove vehicle info from hass.data so that vehicle will not be found
    hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR].data = []

    with pytest.raises(AssertionError):
        await get_diagnostics_for_device(hass, hass_client, config_entry, reg_device)
