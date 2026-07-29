"""Tests for Nature Remo integration setup."""

from dataclasses import replace
from unittest.mock import AsyncMock

from aionatureremo import Appliance, NatureRemoAuthError, NatureRemoConnectionError

from homeassistant.components.nature_remo.const import DOMAIN
from homeassistant.components.nature_remo.coordinator import NatureRemoCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import async_poll

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The entry loads, stores a coordinator, and unloads cleanly."""
    assert init_integration.state is ConfigEntryState.LOADED
    coordinator = init_integration.runtime_data
    assert isinstance(coordinator, NatureRemoCoordinator)
    assert "appliance-ac-1" in coordinator.data.appliances

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_energy_only_hub_is_registered(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A Remo E lite with no sensor events is still registered.

    It reports no te/hu/il/mo events, so no device-scoped entity is ever created
    for it; without eager registration its hub device would be missing.
    """
    device_registry = dr.async_get(hass)

    hub = device_registry.async_get_device(identifiers={(DOMAIN, "device-remoe-1")})
    assert hub is not None
    assert hub.manufacturer == "Nature"
    assert hub.model == "Remo-E-lite"
    assert hub.sw_version == "1.7.2"
    assert hub.serial_number == "4W123456789012"
    assert hub.configuration_url == "https://home.nature.global/"
    assert (dr.CONNECTION_NETWORK_MAC, "ab:cd:ef:12:34:59") in hub.connections


async def test_appliance_links_to_its_hub(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Every appliance points at its parent hub via via_device.

    The smart meter under the Remo E lite must be linked to the hub rather than
    orphaned at the top level, regardless of platform setup ordering.
    """
    device_registry = dr.async_get(hass)

    hub = device_registry.async_get_device(identifiers={(DOMAIN, "device-remoe-1")})
    meter = device_registry.async_get_device(
        identifiers={(DOMAIN, "appliance-meter-1")}
    )
    assert hub is not None
    assert meter is not None
    assert meter.via_device_id == hub.id

    remo3 = device_registry.async_get_device(identifiers={(DOMAIN, "device-remo3-1")})
    ac = device_registry.async_get_device(identifiers={(DOMAIN, "appliance-ac-1")})
    assert remo3 is not None
    assert ac is not None
    assert ac.via_device_id == remo3.id


async def test_setup_retries_on_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """A connection failure during first refresh puts the entry in retry."""
    mock_client.get_devices.side_effect = NatureRemoConnectionError("refused")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_auth_error_is_setup_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """An auth failure during first refresh marks the entry as errored."""
    mock_client.get_devices.side_effect = NatureRemoAuthError(401, "bad token")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_appliance_rename_reaches_the_device_registry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: AsyncMock,
    appliances: list[Appliance],
) -> None:
    """A nickname edited in the Nature app propagates on the next poll.

    The device would otherwise keep the nickname it happened to have when
    its first entity was created.
    """
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, "appliance-ir-1")})
    assert device is not None
    assert device.name == "Fan"

    mock_client.get_appliances.return_value = [
        replace(appliance, nickname="Ceiling fan")
        if appliance.id == "appliance-ir-1"
        else appliance
        for appliance in appliances
    ]
    await async_poll(hass)

    device = device_registry.async_get_device(identifiers={(DOMAIN, "appliance-ir-1")})
    assert device is not None
    assert device.name == "Ceiling fan"
