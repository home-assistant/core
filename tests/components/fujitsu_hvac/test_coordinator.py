"""Test for the FujitsuHVACCoordinator."""

from unittest.mock import AsyncMock

from ayla_iot_unofficial import AylaAuthError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.fujitsu_hvac.const import API_REFRESH_SECONDS, DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_coordinator_initial_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_devices: list[AsyncMock],
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that coordinator returns the data we expect after the first refresh."""
    mock_ayla_api.async_get_devices.return_value = mock_devices
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_coordinator_one_device_disabled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_devices: list[AsyncMock],
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that coordinator only updates devices that are currently listening."""
    mock_ayla_api.async_get_devices.return_value = mock_devices
    await setup_integration(hass, mock_config_entry)

    for d in mock_devices:
        d.async_update.assert_called_once()
        d.reset_mock()

    entity = entity_registry.async_get(
        entity_registry.async_get_entity_id(
            Platform.CLIMATE, DOMAIN, mock_devices[0].device_serial_number
        )
    )
    entity_registry.async_update_entity(
        entity.entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    freezer.tick(API_REFRESH_SECONDS)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == len(mock_devices) - 1
    mock_devices[0].async_update.assert_not_called()
    mock_devices[1].async_update.assert_called_once()


async def test_coordinator_sign_in_exception_get_devices(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_devices: list[AsyncMock],
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the entities become unavailable if we fail to update them because of an auth error while getting the devices."""
    mock_ayla_api.async_get_devices.return_value = mock_devices
    await setup_integration(hass, mock_config_entry)

    mock_ayla_api.async_get_devices.side_effect = AylaAuthError
    freezer.tick(API_REFRESH_SECONDS)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert all(e.state == STATE_UNAVAILABLE for e in hass.states.async_all())


async def test_coordinator_sign_in_exception_update_device(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_devices: list[AsyncMock],
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the entities become unavailable if we fail to update them because of an auth error while updating the devices."""
    mock_ayla_api.async_get_devices.return_value = mock_devices
    await setup_integration(hass, mock_config_entry)

    for d in mock_devices:
        d.async_update.side_effect = AylaAuthError

    freezer.tick(API_REFRESH_SECONDS)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert all(e.state == STATE_UNKNOWN for e in hass.states.async_all())


async def test_coordinator_token_expired(
    hass: HomeAssistant,
    mock_devices: list[AsyncMock],
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Make sure sign_in is called if the token expired."""
    mock_ayla_api.token_expired = True
    await setup_integration(hass, mock_config_entry)

    # Called once during setup and once during update
    assert mock_ayla_api.async_sign_in.call_count == 2


async def test_coordinator_token_expiring_soon(
    hass: HomeAssistant,
    mock_devices: list[AsyncMock],
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Make sure sign_in is called if the token expired."""
    mock_ayla_api.token_expiring_soon = True
    await setup_integration(hass, mock_config_entry)

    mock_ayla_api.async_refresh_auth.assert_called_once()


@pytest.mark.parametrize("exception", [AylaAuthError, TimeoutError])
async def test_coordinator_setup_exception(
    hass: HomeAssistant,
    mock_devices: list[AsyncMock],
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Make sure that no devices is added if there was an exception while logging in."""
    mock_ayla_api.async_sign_in.side_effect = exception
    await setup_integration(hass, mock_config_entry)

    assert len(hass.states.async_all()) == 0
