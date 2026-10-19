"""Tests for the eGauge integration."""

from datetime import timedelta
from unittest.mock import MagicMock

from egauge_async.exceptions import (
    EgaugeAuthenticationError,
    EgaugeParsingException,
    EgaugePermissionError,
)
from freezegun.api import FrozenDateTimeFactory
from httpx2 import ConnectError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.egauge.const import COORDINATOR_UPDATE_INTERVAL_SECONDS
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_egauge_client: MagicMock,
) -> None:
    """Test successful setup."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_egauge_client.get_device_serial_number.called
    assert mock_egauge_client.get_hostname.called
    assert mock_egauge_client.get_register_info.called


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        (ConnectError, ConfigEntryState.SETUP_RETRY),
        (EgaugeAuthenticationError, ConfigEntryState.SETUP_ERROR),
        (EgaugePermissionError, ConfigEntryState.SETUP_ERROR),
        (EgaugeParsingException, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_egauge_client: MagicMock,
    exception: Exception,
    expected: ConfigEntryState,
) -> None:
    """Test setup with connection error."""
    mock_config_entry.add_to_hass(hass)
    mock_egauge_client.get_device_serial_number.side_effect = exception

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(EgaugeAuthenticationError, id="authentication"),
        pytest.param(EgaugePermissionError, id="permission"),
    ],
)
async def test_setup_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_egauge_client: MagicMock,
    exception: type[Exception],
) -> None:
    """Test an authentication error during setup starts a reauth flow."""
    mock_config_entry.add_to_hass(hass)
    mock_egauge_client.get_device_serial_number.side_effect = exception

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(EgaugeAuthenticationError, id="authentication"),
        pytest.param(EgaugePermissionError, id="permission"),
    ],
)
async def test_update_auth_error_starts_reauth(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_egauge_client: MagicMock,
    exception: type[Exception],
) -> None:
    """Test an authentication error during a refresh starts a reauth flow."""
    assert init_integration.state is ConfigEntryState.LOADED
    mock_egauge_client.get_current_measurements.side_effect = exception

    freezer.tick(timedelta(seconds=COORDINATOR_UPDATE_INTERVAL_SECONDS))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == init_integration.entry_id


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_egauge_client: MagicMock,
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
