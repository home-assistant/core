"""Test the initialization."""

from unittest.mock import AsyncMock, patch

from fyta_cli.fyta_exceptions import (
    FytaAuthentificationError,
    FytaConnectionError,
    FytaPasswordError,
)
import pytest

from homeassistant.components.fyta.const import CONF_EXPIRATION, DOMAIN as FYTA_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import (
    ACCESS_TOKEN,
    EXPIRATION,
    EXPIRATION_OLD,
    PASSWORD,
    USERNAME,
    setup_platform,
    setup_platform_expired,
)

from tests.common import MockConfigEntry


async def test_load_unload(hass: HomeAssistant, mock_fyta_init: AsyncMock) -> None:
    """Test load and unload."""

    entry = await setup_platform(hass, SENSOR_DOMAIN)
    assert entry.state is ConfigEntryState.LOADED

    # what could be a good test?

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "exception",
    [
        FytaAuthentificationError,
        FytaPasswordError,
    ],
)
async def test_invalid_credentials(
    hass: HomeAssistant, exception: Exception, mock_fyta_init: AsyncMock
) -> None:
    """Test FYTA credentials changing."""

    mock_fyta_init.return_value.login.side_effect = exception

    with patch(
        "homeassistant.components.fyta.config_flow.FytaConfigFlow.async_step_reauth",
        return_value={
            "type": FlowResultType.FORM,
            "flow_id": "mock_flow",
            "step_id": "reauth_confirm",
        },
    ) as mock_async_step_reauth:
        await setup_platform_expired(hass, SENSOR_DOMAIN)
        await hass.async_block_till_done()

    mock_async_step_reauth.assert_called_once()


async def test_raise_config_entry_not_ready_when_offline(
    hass: HomeAssistant, mock_fyta_init: AsyncMock
) -> None:
    """Config entry state is SETUP_RETRY when FYTA is offline."""

    mock_fyta_init.return_value.login.side_effect = FytaConnectionError

    mock_entry = MockConfigEntry(
        domain=FYTA_DOMAIN,
        title="fyta_user",
        data={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
            CONF_EXPIRATION: EXPIRATION_OLD.isoformat(),
        },
        minor_version=2,
    )
    mock_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.fyta.PLATFORMS", [SENSOR_DOMAIN]),
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.SETUP_RETRY

    assert hass.config_entries.flow.async_progress() == []


async def test_migrate_config_entry(
    hass: HomeAssistant,
    mock_fyta: AsyncMock,
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
    assert entry.data[CONF_EXPIRATION] == EXPIRATION.isoformat()
