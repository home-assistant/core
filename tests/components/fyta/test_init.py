"""Test the initialization."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

from fyta_cli.fyta_exceptions import (
    FytaAuthentificationError,
    FytaConnectionError,
    FytaPasswordError,
)
import pytest

from homeassistant.components.fyta.const import CONF_EXPIRATION, DOMAIN as FYTA_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant

from . import setup_platform
from .const import ACCESS_TOKEN, EXPIRATION, EXPIRATION_OLD, PASSWORD, USERNAME

from tests.common import MockConfigEntry


async def test_load_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fyta_connector: AsyncMock,
) -> None:
    """Test load and unload."""

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_refresh_expired_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fyta_connector: AsyncMock,
) -> None:
    """Test we refresh an expired token."""

    mock_fyta_connector.expiration = datetime.fromisoformat(EXPIRATION_OLD).replace(
        tzinfo=UTC
    )
    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert len(mock_fyta_connector.login.mock_calls) == 1
    assert mock_config_entry.data[CONF_EXPIRATION] == EXPIRATION


@pytest.mark.parametrize(
    "exception",
    [
        FytaAuthentificationError,
        FytaPasswordError,
    ],
)
async def test_invalid_credentials(
    hass: HomeAssistant,
    exception: Exception,
    mock_config_entry: MockConfigEntry,
    mock_fyta_connector: AsyncMock,
) -> None:
    """Test FYTA credentials changing."""

    mock_fyta_connector.expiration = datetime.fromisoformat(EXPIRATION_OLD).replace(
        tzinfo=UTC
    )
    mock_fyta_connector.login.side_effect = exception

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_raise_config_entry_not_ready_when_offline(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fyta_connector: AsyncMock,
) -> None:
    """Config entry state is SETUP_RETRY when FYTA is offline."""

    mock_fyta_connector.update_all_plants.side_effect = FytaConnectionError

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    assert len(hass.config_entries.flow.async_progress()) == 0


async def test_raise_config_entry_not_ready_when_offline_and_expired(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fyta_connector: AsyncMock,
) -> None:
    """Config entry state is SETUP_RETRY when FYTA is offline and access_token is expired."""

    mock_fyta_connector.login.side_effect = FytaConnectionError
    mock_fyta_connector.expiration = datetime.fromisoformat(EXPIRATION_OLD).replace(
        tzinfo=UTC
    )

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    assert len(hass.config_entries.flow.async_progress()) == 0


async def test_migrate_config_entry_1(
    hass: HomeAssistant,
    mock_fyta_connector: AsyncMock,
) -> None:
    """Test successful migration of entry data."""
    entry = MockConfigEntry(
        domain=FYTA_DOMAIN,
        title=USERNAME,
        data={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    assert entry.version == 1
    assert entry.minor_version == 1

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 1
    assert entry.minor_version == 2
    assert entry.data[CONF_USERNAME] == USERNAME
    assert entry.data[CONF_PASSWORD] == PASSWORD
    assert entry.data[CONF_ACCESS_TOKEN] == ACCESS_TOKEN
    assert entry.data[CONF_EXPIRATION] == EXPIRATION


async def test_migrate_config_entry_2(
    hass: HomeAssistant,
    mock_fyta_connector: AsyncMock,
) -> None:
    """Test successful migration of entry data."""
    entry = MockConfigEntry(
        domain=FYTA_DOMAIN,
        title=USERNAME,
        data={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
            CONF_EXPIRATION: EXPIRATION,
        },
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)

    assert entry.version == 1
    assert entry.minor_version == 2

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 1
    assert entry.minor_version == 2
