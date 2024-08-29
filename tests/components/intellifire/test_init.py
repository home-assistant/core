"""Test the IntelliFire config flow."""

from unittest.mock import AsyncMock, patch

from intellifire4py.exceptions import LoginError

from homeassistant.components.intellifire import CONF_USER_ID
from homeassistant.components.intellifire.const import (
    API_MODE_CLOUD,
    API_MODE_LOCAL,
    CONF_AUTH_COOKIE,
    CONF_CONTROL_MODE,
    CONF_READ_MODE,
    CONF_SERIAL,
    CONF_WEB_CLIENT_ID,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_pseudo_migration_good(
    hass: HomeAssistant, mock_config_entry_old, mock_apis_single_fp
) -> None:
    """With the new library we are going to end up rewriting the config entries."""
    mock_config_entry_old.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_old.entry_id)

    assert mock_config_entry_old.data == {
        "ip_address": "192.168.2.108",
        "api_key": "B5C4DA27AAEF31D1FB21AFF9BFA6BCD2",
        "serial": "3FB284769E4736F30C8973A7ED358123",
        "auth_cookie": "B984F21A6378560019F8A1CDE41B6782",
        "web_client_id": "FA2B1C3045601234D0AE17D72F8E975",
        "user_id": "52C3F9E8B9D3AC99F8E4D12345678901FE9A2BC7D85F7654E28BF98BCD123456",
        "username": "grumpypanda@china.cn",
        "password": "you-stole-my-pandas",
    }


async def test_minor_migration(hass: HomeAssistant, mock_apis_single_fp) -> None:
    """Test the case where we completely fail to initialize."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=1,
        title="Fireplace of testing",
        data={
            CONF_HOST: "11.168.2.218",
            CONF_USERNAME: "grumpypanda@china.cn",
            CONF_PASSWORD: "you-stole-my-pandas",
            CONF_USER_ID: "52C3F9E8B9D3AC99F8E4D12345678901FE9A2BC7D85F7654E28BF98BCD123456",
        },
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state == ConfigEntryState.MIGRATION_ERROR


async def test_init_with_no_username(hass: HomeAssistant, mock_apis_single_fp) -> None:
    """Test the case where we completely fail to initialize."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=2,
        data={
            CONF_IP_ADDRESS: "192.168.2.108",
            # CONF_USERNAME: "grumpypanda@china.cn",
            CONF_PASSWORD: "you-stole-my-pandas",
            CONF_SERIAL: "3FB284769E4736F30C8973A7ED358123",
            CONF_WEB_CLIENT_ID: "FA2B1C3045601234D0AE17D72F8E975",
            CONF_API_KEY: "B5C4DA27AAEF31D1FB21AFF9BFA6BCD2",
            CONF_AUTH_COOKIE: "B984F21A6378560019F8A1CDE41B6782",
            CONF_USER_ID: "52C3F9E8B9D3AC99F8E4D12345678901FE9A2BC7D85F7654E28BF98BCD123456",
        },
        options={CONF_READ_MODE: API_MODE_LOCAL, CONF_CONTROL_MODE: API_MODE_CLOUD},
        unique_id="3FB284769E4736F30C8973A7ED358123",
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state == ConfigEntryState.SETUP_ERROR


async def test_connectivity_bad(
    hass: HomeAssistant,
    mock_config_entry_current,
    mock_apis_single_fp,
) -> None:
    """Test a timeout error on the setup flow."""

    with patch(
        "homeassistant.components.intellifire.UnifiedFireplace.build_fireplace_from_common",
        new_callable=AsyncMock,
        side_effect=TimeoutError,
    ):
        mock_config_entry_current.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_current.entry_id)

        await hass.async_block_till_done()
        assert len(hass.states.async_all()) == 0


async def test_pseudo_migration_bad_title(
    hass: HomeAssistant, mock_config_entry_v1_bad_title, mock_apis_single_fp
) -> None:
    """Test entity update from older Version1 to a newer Version1 with serial that can't be detected."""
    mock_config_entry_v1_bad_title.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v1_bad_title.entry_id)
    assert mock_config_entry_v1_bad_title.state == ConfigEntryState.LOADED

    assert mock_config_entry_v1_bad_title.data == {
        "ip_address": "192.168.2.108",
        "api_key": "B5C4DA27AAEF31D1FB21AFF9BFA6BCD2",
        "serial": "3FB284769E4736F30C8973A7ED358123",
        "auth_cookie": "B984F21A6378560019F8A1CDE41B6782",
        "web_client_id": "FA2B1C3045601234D0AE17D72F8E975",
        "user_id": "52C3F9E8B9D3AC99F8E4D12345678901FE9A2BC7D85F7654E28BF98BCD123456",
        "username": "grumpypanda@china.cn",
        "password": "you-stole-my-pandas",
    }


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry_current,
    mock_apis_single_fp,
) -> None:
    """Test reauth."""

    mock_local_interface, mock_cloud_interface, mock_fp = mock_apis_single_fp
    # Set login error
    mock_cloud_interface.login_with_credentials.side_effect = LoginError

    mock_config_entry_current.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": "reauth",
            "unique_id": mock_config_entry_current.unique_id,
            "entry_id": mock_config_entry_current.entry_id,
        },
    )
    assert result["type"] == FlowResultType.FORM
    result["step_id"] = "cloud_api"
