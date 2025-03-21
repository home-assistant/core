"""Tests for Intergas InComfort integration."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientResponseError, RequestInfo
from freezegun.api import FrozenDateTimeFactory
from incomfortclient import InvalidGateway, InvalidHeaterList
import pytest

from homeassistant.components.incomfort import DOMAIN
from homeassistant.components.incomfort.coordinator import UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceRegistry

from .conftest import MOCK_HEATER_STATUS

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_setup_platforms(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the incomfort integration is set up correctly."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "mock_heater_status", [MOCK_HEATER_STATUS | {"serial_no": "c01d00c0ffee"}]
)
async def test_stale_devices_cleanup(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mock_incomfort: MagicMock,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_heater_status: dict[str, Any],
) -> None:
    """Test the incomfort integration is cleaning up stale devices."""
    # Setup an old heater with serial_no c01d00c0ffee
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    old_entries = device_registry.devices.get_devices_for_config_entry_id(
        mock_config_entry.entry_id
    )
    assert len(old_entries) == 3
    old_heater = device_registry.async_get_device({(DOMAIN, "c01d00c0ffee")})
    assert old_heater is not None
    assert old_heater.serial_number == "c01d00c0ffee"
    old_climate = device_registry.async_get_device({(DOMAIN, "c01d00c0ffee_1")})
    assert old_heater is not None
    old_climate = device_registry.async_get_device({(DOMAIN, "c01d00c0ffee_1")})
    assert old_climate is not None

    mock_heater_status["serial_no"] = "c0ffeec0ffee"
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    new_entries = device_registry.devices.get_devices_for_config_entry_id(
        mock_config_entry.entry_id
    )
    assert len(new_entries) == 3
    new_heater = device_registry.async_get_device({(DOMAIN, "c0ffeec0ffee")})
    assert new_heater is not None
    assert new_heater.serial_number == "c0ffeec0ffee"
    new_climate = device_registry.async_get_device({(DOMAIN, "c0ffeec0ffee_1")})
    assert new_climate is not None

    old_heater = device_registry.async_get_device({(DOMAIN, "c01d00c0ffee")})
    assert old_heater is None
    old_climate = device_registry.async_get_device({(DOMAIN, "c01d00c0ffee_1")})
    assert old_climate is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_coordinator_updates(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test the incomfort coordinator is updating."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    state = hass.states.get("climate.thermostat_1")
    assert state is not None
    assert state.attributes["current_temperature"] == 21.4
    mock_incomfort().mock_room_status["room_temp"] = 20.91

    state = hass.states.get("sensor.boiler_pressure")
    assert state is not None
    assert state.state == "1.86"
    mock_incomfort().mock_heater_status["pressure"] = 1.84

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL + 5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("climate.thermostat_1")
    assert state is not None
    assert state.attributes["current_temperature"] == 20.9

    state = hass.states.get("sensor.boiler_pressure")
    assert state is not None
    assert state.state == "1.84"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "exc",
    [
        ClientResponseError(
            RequestInfo(
                url="http://example.com",
                method="GET",
                headers=[],
                real_url="http://example.com",
            ),
            None,
            status=401,
        ),
        InvalidHeaterList,
        ClientResponseError(
            RequestInfo(
                url="http://example.com",
                method="GET",
                headers=[],
                real_url="http://example.com",
            ),
            None,
            status=500,
        ),
        TimeoutError,
    ],
)
async def test_coordinator_update_fails(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    freezer: FrozenDateTimeFactory,
    exc: Exception,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test the incomfort coordinator update fails."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    state = hass.states.get("sensor.boiler_pressure")
    assert state is not None
    assert state.state == "1.86"

    with patch.object(
        mock_incomfort().heaters.return_value[0], "update", side_effect=exc
    ):
        freezer.tick(timedelta(seconds=UPDATE_INTERVAL + 5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("sensor.boiler_pressure")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("exc", "config_entry_state"),
    [
        (
            InvalidGateway,
            ConfigEntryState.SETUP_ERROR,
        ),
        (InvalidHeaterList, ConfigEntryState.SETUP_RETRY),
        (
            ClientResponseError(
                RequestInfo(
                    url="http://example.com",
                    method="GET",
                    headers=[],
                    real_url="http://example.com",
                ),
                None,
                status=404,
            ),
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            ClientResponseError(
                RequestInfo(
                    url="http://example.com",
                    method="GET",
                    headers=[],
                    real_url="http://example.com",
                ),
                None,
                status=500,
            ),
            ConfigEntryState.SETUP_RETRY,
        ),
        (TimeoutError, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_entry_setup_fails(
    hass: HomeAssistant,
    mock_incomfort: MagicMock,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: ConfigEntry,
    exc: Exception,
    config_entry_state: ConfigEntryState,
) -> None:
    """Test the incomfort coordinator entry setup fails."""
    with patch(
        "homeassistant.components.incomfort.async_connect_gateway",
        AsyncMock(side_effect=exc),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
    state = hass.states.get("sensor.boiler_pressure")
    assert state is None
    assert mock_config_entry.state is config_entry_state
