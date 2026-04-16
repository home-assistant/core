"""Test the Fresh-r initialization."""

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
from pyfreshr.exceptions import ApiResponseError, LoginError
import pytest

from homeassistant.components.freshr.const import DOMAIN
from homeassistant.components.freshr.coordinator import (
    DEVICES_SCAN_INTERVAL,
    READINGS_SCAN_INTERVAL,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import DEVICE_ID, MagicMock, MockConfigEntry

from tests.common import async_fire_time_changed


@pytest.mark.usefixtures("init_integration")
async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading the config entry."""
    assert mock_config_entry.state is ConfigEntryState.LOADED
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "entry_state"),
    [
        (ApiResponseError("parse error"), ConfigEntryState.SETUP_RETRY),
        (ClientError("network error"), ConfigEntryState.SETUP_RETRY),
        (LoginError("bad credentials"), ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_freshr_client: MagicMock,
    exception: Exception,
    entry_state: ConfigEntryState,
) -> None:
    """Test that an error during setup sets the config entry to the expected state."""
    mock_freshr_client.fetch_devices.side_effect = exception
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is entry_state


async def test_setup_no_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_freshr_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that an empty device list sets up successfully with no entities."""
    mock_freshr_client.fetch_devices.return_value = []
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert (
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
        == []
    )


@pytest.mark.usefixtures("init_integration")
async def test_stale_device_removed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_freshr_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a device absent from a successful poll is removed from the registry."""
    assert device_registry.async_get_device(identifiers={(DOMAIN, DEVICE_ID)})

    mock_freshr_client.fetch_devices.return_value = []
    freezer.tick(DEVICES_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert device_registry.async_get_device(identifiers={(DOMAIN, DEVICE_ID)}) is None

    call_count = mock_freshr_client.fetch_device_current.call_count
    freezer.tick(READINGS_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_freshr_client.fetch_device_current.call_count == call_count


@pytest.mark.usefixtures("init_integration")
async def test_stale_device_not_removed_on_poll_error(
    hass: HomeAssistant,
    mock_freshr_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a device is not removed when the devices poll fails."""
    assert device_registry.async_get_device(identifiers={(DOMAIN, DEVICE_ID)})

    mock_freshr_client.fetch_devices.side_effect = ApiResponseError("cloud error")
    freezer.tick(DEVICES_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert device_registry.async_get_device(identifiers={(DOMAIN, DEVICE_ID)})


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_readings_login_error_triggers_reauth(
    hass: HomeAssistant,
    mock_freshr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a LoginError during readings refresh triggers a reauth flow."""
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)

    mock_freshr_client.fetch_device_current.reset_mock()
    mock_freshr_client.fetch_device_current.side_effect = LoginError("session expired")
    freezer.tick(READINGS_SCAN_INTERVAL)
    async_fire_time_changed(hass, freezer())
    await hass.async_block_till_done()

    assert mock_freshr_client.fetch_device_current.called

    assert mock_config_entry.state is ConfigEntryState.LOADED

    entity_ids = [
        entry.entity_id
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    ]
    assert entity_ids
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        assert state is not None, f"State for {entity_id} is None"
        assert state.state == STATE_UNAVAILABLE, (
            f"Expected {entity_id} to be {STATE_UNAVAILABLE!r}, got {state.state!r}"
        )

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    relevant_flows = [
        {
            "entry_id": flow.get("context", {}).get("entry_id"),
            "source": flow.get("context", {}).get("source"),
            "step_id": flow.get("step_id"),
        }
        for flow in flows
    ]
    assert any(
        flow["entry_id"] == mock_config_entry.entry_id
        and flow["source"] == SOURCE_REAUTH
        and flow["step_id"] == "reauth_confirm"
        for flow in relevant_flows
    ), (
        "Expected a reauth_confirm flow for the config entry, "
        f"but found flows: {relevant_flows}"
    )
