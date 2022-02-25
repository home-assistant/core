"""Test Lidarr config flow."""
from unittest.mock import patch

from aiopyarr import ArrAuthenticationException, ArrConnectionException, ArrException

from homeassistant import data_entry_flow
from homeassistant.components.lidarr.const import (
    CONF_MAX_RECORDS,
    CONF_UPCOMING_DAYS,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_SOURCE
from homeassistant.core import HomeAssistant

from . import CONF_DATA, MOCK_USER_INPUT, create_entry, mock_connection

from tests.test_util.aiohttp import AiohttpClientMocker


def _patch_client():
    return patch(
        "homeassistant.components.lidarr.config_flow.LidarrClient.async_get_system_status"
    )


async def test_flow_user_form(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the user set up form is served."""
    mock_connection(aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_INPUT,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == CONF_DATA
    assert result["options"] == {CONF_MAX_RECORDS: 1000, CONF_UPCOMING_DAYS: 7}


async def test_flow_user_invalid_auth(hass: HomeAssistant) -> None:
    """Test invalid authentication."""
    with _patch_client() as client:
        client.side_effect = ArrAuthenticationException
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "invalid_auth"


async def test_flow_user_cannot_connect(hass: HomeAssistant) -> None:
    """Test connection error."""
    with _patch_client() as client:
        client.side_effect = ArrConnectionException
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "cannot_connect"


async def test_flow_user_unknown_error(hass: HomeAssistant) -> None:
    """Test unknown error."""
    with _patch_client() as client:
        client.side_effect = ArrException
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "unknown"


async def test_flow_user_failed_zeroconf(hass: HomeAssistant) -> None:
    """Test zero configuration failed."""
    with _patch_client() as client:
        client.return_value = "zeroconf_failed"
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "zeroconf_failed"


async def test_flow_reauth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test reauth."""
    entry = create_entry(hass)
    mock_connection(aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            CONF_SOURCE: SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
        data=CONF_DATA,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "abc123"},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == "abc123"


async def test_options_flow(
    hass: HomeAssistant,
):
    """Test updating options."""
    entry = create_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_UPCOMING_DAYS: 2, CONF_MAX_RECORDS: 100},
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_UPCOMING_DAYS] == 2
    assert result["data"][CONF_MAX_RECORDS] == 100
