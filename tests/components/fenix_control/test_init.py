"""Test the FENIX Control setup and coordinator."""

from dataclasses import replace
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyfenixcontrol import (
    FenixControlAuthError,
    FenixControlConnectionError,
    FenixControlResponseError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fenix_control.const import DOMAIN, SCAN_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import DEVICE, DEVICE_ID, INSTALLATION_ID

ENTITY_ID = "climate.home_living_room"


async def test_setup_and_unload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_fenix_client: MagicMock,
) -> None:
    """Test setting up and unloading the integration."""
    assert init_integration.state is ConfigEntryState.LOADED
    mock_fenix_client.trigger_installation_update.assert_awaited_once_with(
        INSTALLATION_ID
    )
    # The device states are read after the update trigger
    assert [call[0] for call in mock_fenix_client.mock_calls] == [
        "get_installations",
        "trigger_installation_update",
        "get_devices",
    ]

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "state"),
    [
        pytest.param(
            FenixControlAuthError("rejected"),
            ConfigEntryState.SETUP_ERROR,
            id="auth",
        ),
        pytest.param(
            FenixControlConnectionError("offline"),
            ConfigEntryState.SETUP_RETRY,
            id="connection",
        ),
        pytest.param(
            FenixControlResponseError("HTTP 503", 503),
            ConfigEntryState.SETUP_RETRY,
            id="response",
        ),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fenix_client: MagicMock,
    side_effect: Exception,
    state: ConfigEntryState,
) -> None:
    """Test setup failures."""
    mock_fenix_client.get_installations.side_effect = side_effect
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is state


async def test_setup_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fenix_client: MagicMock,
) -> None:
    """Test a rejected login starts the reauthentication flow."""
    mock_fenix_client.get_installations.side_effect = FenixControlAuthError("expired")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


async def test_update_trigger_failure_is_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fenix_client: MagicMock,
) -> None:
    """Test a rejected update trigger doesn't fail the update."""
    mock_fenix_client.trigger_installation_update.side_effect = (
        FenixControlResponseError("HTTP 500", 500)
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("init_integration")
async def test_update_trigger_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_fenix_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an auth error from the update trigger starts reauthentication."""
    mock_fenix_client.trigger_installation_update.side_effect = FenixControlAuthError(
        "expired"
    )

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


async def test_device_info(
    device_registry: dr.DeviceRegistry,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the thermostat is registered as a device."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, DEVICE_ID), init_integration.entry_id
    )
    assert device == snapshot


async def test_device_name_falls_back_to_room(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_fenix_client: MagicMock,
) -> None:
    """Test a thermostat without its own name is named after its room."""
    mock_fenix_client.get_devices.return_value = [replace(DEVICE, name=None)]
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, DEVICE_ID), mock_config_entry.entry_id
    )
    assert device.name == "Home Living room"
    assert hass.states.get(ENTITY_ID) is not None
