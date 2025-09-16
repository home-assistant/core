"""Tests for Renault setup process."""

from collections.abc import Generator
from typing import Any
from unittest.mock import Mock, patch

import aiohttp
import pytest
from renault_api.gigya.exceptions import GigyaException, InvalidCredentialsException
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.renault.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.renault.PLATFORMS", []):
        yield


@pytest.mark.usefixtures("patch_renault_account", "patch_get_vehicles")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_setup_unload_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Test entry setup and unload."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.LOADED

    # Unload the entry and verify that the data has been removed
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_bad_password(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Test entry setup and unload."""
    # Create a mock entry so we don't have to go through config flow
    with patch(
        "renault_api.renault_session.RenaultSession.login",
        side_effect=InvalidCredentialsException(403042, "invalid loginID or password"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == config_entry.entry_id


@pytest.mark.parametrize("side_effect", [aiohttp.ClientConnectionError, GigyaException])
async def test_setup_entry_exception(
    hass: HomeAssistant, config_entry: ConfigEntry, side_effect: Any
) -> None:
    """Test ConfigEntryNotReady when API raises an exception during entry setup."""
    # In this case we are testing the condition where async_setup_entry raises
    # ConfigEntryNotReady.
    with patch(
        "renault_api.renault_session.RenaultSession.login",
        side_effect=side_effect,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("patch_renault_account")
async def test_setup_entry_kamereon_exception(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Test ConfigEntryNotReady when API raises an exception during entry setup."""
    # In this case we are testing the condition where renault_hub fails to retrieve
    # list of vehicles (see Gateway Time-out on #97324).
    with patch(
        "renault_api.renault_client.RenaultClient.get_api_account",
        side_effect=aiohttp.ClientResponseError(Mock(), (), status=504),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("patch_renault_account", "patch_get_vehicles")
@pytest.mark.parametrize("vehicle_type", ["missing_details"], indirect=True)
async def test_setup_entry_missing_vehicle_details(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Test ConfigEntryNotReady when vehicleDetails is missing."""
    # In this case we are testing the condition where renault_hub fails to retrieve
    # vehicle details (see #99127).
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("patch_renault_account", "patch_get_vehicles")
async def test_device_registry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device is correctly registered."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Ensure devices are correctly registered
    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )
    assert device_entries == snapshot


@pytest.mark.usefixtures("patch_renault_account", "patch_get_vehicles")
@pytest.mark.parametrize("vehicle_type", ["zoe_40"], indirect=True)
async def test_registry_cleanup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: ConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test being able to remove a disconnected device."""
    assert await async_setup_component(hass, "config", {})
    entry_id = config_entry.entry_id
    live_id = "VF1ZOE40VIN"
    dead_id = "VF1AAAAA555777888"

    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 0
    device_registry.async_get_or_create(
        config_entry_id=entry_id,
        identifiers={(DOMAIN, dead_id)},
        manufacturer="Renault",
        model="Zoe",
        name="REGISTRATION-NUMBER",
        sw_version="X101VE",
    )
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 1

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 2

    # Try to remove "VF1ZOE40VIN" - fails as it is live
    device = device_registry.async_get_device(identifiers={(DOMAIN, live_id)})
    client = await hass_ws_client(hass)
    response = await client.remove_device(device.id, entry_id)
    assert not response["success"]
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 2
    assert device_registry.async_get_device(identifiers={(DOMAIN, live_id)}) is not None

    # Try to remove "VF1AAAAA555777888" - succeeds as it is dead
    device = device_registry.async_get_device(identifiers={(DOMAIN, dead_id)})
    response = await client.remove_device(device.id, entry_id)
    assert response["success"]
    assert len(dr.async_entries_for_config_entry(device_registry, entry_id)) == 1
    assert device_registry.async_get_device(identifiers={(DOMAIN, dead_id)}) is None
