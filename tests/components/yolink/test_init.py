"""Tests for the yolink integration."""

from unittest.mock import AsyncMock, patch

import pytest
from yolink.const import OAUTH2_TOKEN
from yolink.exception import YoLinkAuthFailError, YoLinkClientError
from yolink.model import BRDP

from homeassistant.components.yolink.api import UACAuth
from homeassistant.components.yolink.const import (
    AUTH_TYPE_UAC,
    CONF_AUTH_TYPE,
    CONF_HOME_ID,
    CONF_SECRET_KEY,
    CONF_UAID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from .conftest import TEST_SECRET_KEY, TEST_UAID, build_yolink_home, home_info_response

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.usefixtures("setup_credentials", "mock_auth_manager", "mock_yolink_home")
async def test_device_remove_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we can only remove a device that no longer exists."""

    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "stale_device_id")},
    )
    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )

    assert len(device_entries) == 1
    device_entry = device_entries[0]
    assert device_entry.identifiers == {(DOMAIN, "stale_device_id")}

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(device_entries) == 0


@pytest.mark.usefixtures("setup_credentials", "mock_yolink_home")
async def test_oauth_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an entry predating UAC support is set up over OAuth2."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("setup_credentials", "mock_yolink_home")
async def test_oauth_implementation_not_available(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that an unavailable OAuth2 implementation raises ConfigEntryNotReady."""
    with patch(
        "homeassistant.components.yolink.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_uac_setup_and_unload(
    hass: HomeAssistant,
    mock_uac_config_entry: MockConfigEntry,
    mock_yolink_home: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test UAC config entry setup and unload."""
    assert await hass.config_entries.async_setup(mock_uac_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_uac_config_entry.state is ConfigEntryState.LOADED
    # The home id is already known, so it is not looked up again.
    mock_yolink_home.return_value.async_get_home_info.assert_not_awaited()

    auth_mgr = mock_yolink_home.return_value.async_setup.await_args.args[0]
    assert isinstance(auth_mgr, UACAuth)

    # The credentials of the entry are the ones the manager authenticates with.
    aioclient_mock.post(
        OAUTH2_TOKEN, json={"access_token": "token-1", "expires_in": 7200}
    )
    assert await auth_mgr.check_and_refresh_token() == "token-1"
    assert aioclient_mock.mock_calls[0][2] == {
        "grant_type": "client_credentials",
        "scope": "create",
        "client_id": TEST_UAID,
        "client_secret": TEST_SECRET_KEY,
    }

    assert await hass.config_entries.async_unload(mock_uac_config_entry.entry_id)
    assert mock_uac_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_yolink_home.return_value.async_unload.assert_awaited_once()


async def test_uac_entries_are_isolated(
    hass: HomeAssistant,
    mock_uac_config_entry: MockConfigEntry,
    mock_yolink_home: AsyncMock,
) -> None:
    """Test loaded entries do not share their home or authentication."""
    second_entry = MockConfigEntry(
        unique_id="home_22222",
        domain=DOMAIN,
        title="Second Home",
        data={
            CONF_AUTH_TYPE: AUTH_TYPE_UAC,
            CONF_UAID: "second-uaid",
            CONF_SECRET_KEY: "second-secret",
            CONF_HOME_ID: "home_22222",
        },
    )
    second_entry.add_to_hass(hass)
    mock_yolink_home.side_effect = build_yolink_home

    # Setting up the component loads every entry of the domain.
    assert await hass.config_entries.async_setup(mock_uac_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_uac_config_entry.state is ConfigEntryState.LOADED
    assert second_entry.state is ConfigEntryState.LOADED

    first_home = mock_uac_config_entry.runtime_data.home_instance
    second_home = second_entry.runtime_data.home_instance
    assert first_home is not second_home

    first_auth = first_home.async_setup.await_args.args[0]
    second_auth = second_home.async_setup.await_args.args[0]
    assert first_auth is not second_auth

    assert await hass.config_entries.async_unload(second_entry.entry_id)
    await hass.async_block_till_done()

    assert second_entry.state is ConfigEntryState.NOT_LOADED
    second_home.async_unload.assert_awaited_once()
    assert mock_uac_config_entry.state is ConfigEntryState.LOADED
    first_home.async_unload.assert_not_awaited()


@pytest.mark.usefixtures("setup_credentials")
async def test_setup_records_home_id_of_legacy_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yolink_home: AsyncMock,
) -> None:
    """Test an entry predating the home id records it on setup."""
    mock_yolink_home.return_value.async_get_home_info.return_value = home_info_response(
        "home_99999"
    )
    assert CONF_HOME_ID not in mock_config_entry.data

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.data[CONF_HOME_ID] == "home_99999"


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(YoLinkClientError("-1003", "Request failed"), id="client_error"),
        pytest.param(
            YoLinkAuthFailError("000103", "Invalid credentials"), id="auth_error"
        ),
        pytest.param(TimeoutError(), id="timeout"),
    ],
)
@pytest.mark.usefixtures("setup_credentials")
async def test_setup_survives_failing_home_id_lookup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yolink_home: AsyncMock,
    side_effect: Exception,
) -> None:
    """Test recording the home id does not fail an otherwise working setup."""
    mock_yolink_home.return_value.async_get_home_info.side_effect = side_effect

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    # A later start records the home again.
    assert CONF_HOME_ID not in mock_config_entry.data


@pytest.mark.usefixtures("setup_credentials")
async def test_setup_without_home_info_in_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yolink_home: AsyncMock,
) -> None:
    """Test a home info response naming no home does not fail setup."""
    mock_yolink_home.return_value.async_get_home_info.return_value = BRDP(code="000000")

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert CONF_HOME_ID not in mock_config_entry.data


async def test_uac_setup_auth_failure(
    hass: HomeAssistant,
    mock_uac_config_entry: MockConfigEntry,
    mock_yolink_home: AsyncMock,
) -> None:
    """Test a UAC authentication failure starts a reauthentication flow."""
    mock_yolink_home.return_value.async_setup.side_effect = YoLinkAuthFailError(
        "000103", "Invalid credentials"
    )

    await hass.config_entries.async_setup(mock_uac_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_uac_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_uac_config_entry.entry_id


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(YoLinkClientError("000201", "Connection failed"), id="client"),
        pytest.param(TimeoutError(), id="timeout"),
    ],
)
async def test_uac_setup_connection_failure(
    hass: HomeAssistant,
    mock_uac_config_entry: MockConfigEntry,
    mock_yolink_home: AsyncMock,
    side_effect: Exception,
) -> None:
    """Test a UAC connection failure is retried."""
    mock_yolink_home.return_value.async_setup.side_effect = side_effect

    await hass.config_entries.async_setup(mock_uac_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_uac_config_entry.state is ConfigEntryState.SETUP_RETRY
