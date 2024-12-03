"""Test the initialization."""

from unittest.mock import AsyncMock

import pytest
from solarlog_cli.solarlog_exceptions import (
    SolarLogAuthenticationError,
    SolarLogConnectionError,
    SolarLogError,
    SolarLogUpdateError,
)

from homeassistant.components.solarlog.const import CONF_HAS_PWD, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import setup_platform
from .const import HOST

from tests.common import MockConfigEntry


async def test_load_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_solarlog_connector: AsyncMock,
) -> None:
    """Test load and unload."""

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (SolarLogAuthenticationError, ConfigEntryState.SETUP_ERROR),
        (SolarLogUpdateError, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_error(
    hass: HomeAssistant,
    exception: SolarLogError,
    error: str,
    mock_config_entry: MockConfigEntry,
    mock_solarlog_connector: AsyncMock,
) -> None:
    """Test errors in setting up coordinator (i.e. login error)."""

    mock_solarlog_connector.login.side_effect = exception

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    await hass.async_block_till_done()

    assert mock_config_entry.state == error

    if error == ConfigEntryState.SETUP_RETRY:
        assert len(hass.config_entries.flow.async_progress()) == 0


@pytest.mark.parametrize(
    ("login_side_effect", "login_return_value", "entry_state"),
    [
        (SolarLogAuthenticationError, False, ConfigEntryState.SETUP_ERROR),
        (ConfigEntryNotReady, False, ConfigEntryState.SETUP_RETRY),
        (None, False, ConfigEntryState.SETUP_ERROR),
        (None, True, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_auth_error_during_first_refresh(
    hass: HomeAssistant,
    login_side_effect: Exception | None,
    login_return_value: bool,
    entry_state: str,
    mock_config_entry: MockConfigEntry,
    mock_solarlog_connector: AsyncMock,
) -> None:
    """Test the correct exceptions are thrown for auth error during first refresh."""

    mock_solarlog_connector.password.return_value = ""
    mock_solarlog_connector.update_data.side_effect = SolarLogAuthenticationError

    mock_solarlog_connector.login.return_value = login_return_value
    mock_solarlog_connector.login.side_effect = login_side_effect

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    await hass.async_block_till_done()

    assert mock_config_entry.state == entry_state


@pytest.mark.parametrize(
    ("exception"),
    [
        (SolarLogConnectionError),
        (SolarLogUpdateError),
    ],
)
async def test_other_exceptions_during_first_refresh(
    hass: HomeAssistant,
    exception: SolarLogError,
    mock_config_entry: MockConfigEntry,
    mock_solarlog_connector: AsyncMock,
) -> None:
    """Test the correct exceptions are thrown during first refresh."""

    mock_solarlog_connector.update_data.side_effect = exception

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY

    assert len(hass.config_entries.flow.async_progress()) == 0


@pytest.mark.parametrize(
    ("minor_version", "suffix"),
    [
        (1, "time"),
        (2, "last_updated"),
    ],
)
async def test_migrate_config_entry(
    hass: HomeAssistant,
    minor_version: int,
    suffix: str,
    device_registry: DeviceRegistry,
    entity_registry: EntityRegistry,
    mock_solarlog_connector: AsyncMock,
) -> None:
    """Test successful migration of entry data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=HOST,
        data={
            CONF_HOST: HOST,
        },
        version=1,
        minor_version=minor_version,
    )
    entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="Solar-Log",
        name="solarlog",
    )
    uid = f"{entry.entry_id}_{suffix}"

    sensor_entity = entity_registry.async_get_or_create(
        config_entry=entry,
        platform=DOMAIN,
        domain=Platform.SENSOR,
        unique_id=uid,
        device_id=device.id,
    )

    assert entry.version == 1
    assert entry.minor_version == minor_version
    assert sensor_entity.unique_id == f"{entry.entry_id}_{suffix}"

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_migrated = entity_registry.async_get(sensor_entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == f"{entry.entry_id}_last_updated"

    assert entry.version == 1
    assert entry.minor_version == 3
    assert entry.data[CONF_HOST] == HOST
    assert entry.data[CONF_HAS_PWD] is False
