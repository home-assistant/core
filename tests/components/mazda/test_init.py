"""Tests for the Mazda Connected Services integration."""
from datetime import timedelta
import json
from unittest.mock import patch

from pymazda import MazdaAuthenticationException, MazdaException

from homeassistant.components.mazda.const import DOMAIN
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_ERROR,
    ENTRY_STATE_SETUP_RETRY,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_REGION
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture
from tests.components.mazda import init_integration

FIXTURE_USER_INPUT = {
    CONF_EMAIL: "example@example.com",
    CONF_PASSWORD: "password",
    CONF_REGION: "MNAO",
}


async def test_config_entry_not_ready(hass: HomeAssistant) -> None:
    """Test the Mazda configuration entry not ready."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=FIXTURE_USER_INPUT)
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.mazda.MazdaAPI.validate_credentials",
        side_effect=MazdaException("Unknown error"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ENTRY_STATE_SETUP_RETRY


async def test_init_auth_failure(hass: HomeAssistant):
    """Test auth failure during setup."""
    with patch(
        "homeassistant.components.mazda.MazdaAPI.validate_credentials",
        side_effect=MazdaAuthenticationException("Login failed"),
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=FIXTURE_USER_INPUT)
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state == ENTRY_STATE_SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "user"


async def test_update_auth_failure(hass: HomeAssistant):
    """Test auth failure during data update."""
    get_vehicles_fixture = json.loads(load_fixture("mazda/get_vehicles.json"))
    get_vehicle_status_fixture = json.loads(
        load_fixture("mazda/get_vehicle_status.json")
    )

    with patch(
        "homeassistant.components.mazda.MazdaAPI.validate_credentials",
        return_value=True,
    ), patch(
        "homeassistant.components.mazda.MazdaAPI.get_vehicles",
        return_value=get_vehicles_fixture,
    ), patch(
        "homeassistant.components.mazda.MazdaAPI.get_vehicle_status",
        return_value=get_vehicle_status_fixture,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=FIXTURE_USER_INPUT)
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state == ENTRY_STATE_LOADED

    with patch(
        "homeassistant.components.mazda.MazdaAPI.get_vehicles",
        side_effect=MazdaAuthenticationException("Login failed"),
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
        await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "user"


async def test_unload_config_entry(hass: HomeAssistant) -> None:
    """Test the Mazda configuration entry unloading."""
    entry = await init_integration(hass)
    assert hass.data[DOMAIN]

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ENTRY_STATE_NOT_LOADED


async def test_device_nickname(hass):
    """Test creation of the device when vehicle has a nickname."""
    await init_integration(hass, use_nickname=True)

    device_registry = dr.async_get(hass)
    reg_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "JM000000000000000")},
    )

    assert reg_device.model == "2021 MAZDA3 2.5 S SE AWD"
    assert reg_device.manufacturer == "Mazda"
    assert reg_device.name == "My Mazda3"


async def test_device_no_nickname(hass):
    """Test creation of the device when vehicle has no nickname."""
    await init_integration(hass, use_nickname=False)

    device_registry = dr.async_get(hass)
    reg_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "JM000000000000000")},
    )

    assert reg_device.model == "2021 MAZDA3 2.5 S SE AWD"
    assert reg_device.manufacturer == "Mazda"
    assert reg_device.name == "2021 MAZDA3 2.5 S SE AWD"
