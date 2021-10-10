"""Test Tautulli config flow."""
from unittest.mock import patch

from pytautulli import exceptions

from homeassistant import data_entry_flow
from homeassistant.components.tautulli.const import (
    CONF_MONITORED_USERS,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_SOURCE
from homeassistant.core import HomeAssistant

from . import (
    CONF_DATA,
    CONF_DATA_ADVANCED,
    DEFAULT_USERS,
    NAME,
    SELECTED_USERNAMES,
    UNIQUE_ID,
    _create_mocked_tautulli,
    _patch_config_flow_tautulli,
    setup_integration,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


def _patch_setup():
    return patch("homeassistant.components.tautulli.async_setup_entry")


async def test_flow_user(hass: HomeAssistant):
    """Test user initiated flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER, "show_advanced_options": True}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    mocked_tautulli = await _create_mocked_tautulli()
    with _patch_config_flow_tautulli(mocked_tautulli), _patch_setup():
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == NAME
    assert result2["data"] == CONF_DATA_ADVANCED
    assert result2["result"].unique_id == UNIQUE_ID


async def test_flow_user_cannot_connect(hass: HomeAssistant):
    """Test user initialized flow with unreachable server."""
    with _patch_config_flow_tautulli(await _create_mocked_tautulli()) as tautullimock:
        tautullimock.side_effect = exceptions.PyTautulliConnectionException
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data=CONF_DATA
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "cannot_connect"


async def test_flow_user_invalid_auth(hass: HomeAssistant):
    """Test user initialized flow with invalid authentication."""
    with _patch_config_flow_tautulli(await _create_mocked_tautulli()) as tautullimock:
        tautullimock.side_effect = exceptions.PyTautulliAuthenticationException
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "invalid_auth"


async def test_flow_user_unknown_error(hass: HomeAssistant):
    """Test user initialized flow with unreachable server."""
    with _patch_config_flow_tautulli(await _create_mocked_tautulli()) as tautullimock:
        tautullimock.side_effect = Exception
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data=CONF_DATA
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "unknown"


async def test_flow_reauth(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker):
    """Test reauth flow."""
    with patch("homeassistant.components.tautulli.PLATFORMS", []):
        entry = await setup_integration(hass, aioclient_mock)
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
    assert result["errors"] == {}

    new_conf = {CONF_API_KEY: "efgh"}
    CONF_DATA_ADVANCED[CONF_API_KEY] = "efgh"
    mocked_tautulli = await _create_mocked_tautulli()
    with _patch_config_flow_tautulli(mocked_tautulli), _patch_setup() as mock_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=new_conf,
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data == CONF_DATA_ADVANCED
    assert len(mock_entry.mock_calls) == 1


async def test_flow_reauth_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    """Test reauth flow with invalid authentication."""
    with patch("homeassistant.components.tautulli.PLATFORMS", []):
        entry = await setup_integration(hass, aioclient_mock)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
    )
    with _patch_config_flow_tautulli(await _create_mocked_tautulli()) as tautullimock:
        tautullimock.side_effect = exceptions.PyTautulliAuthenticationException
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "efgh"},
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"]["base"] == "invalid_auth"


async def test_options_flow(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker):
    """Test updating options."""
    with patch("homeassistant.components.tautulli.PLATFORMS", []):
        entry = await setup_integration(hass, aioclient_mock)
    assert entry.options[CONF_MONITORED_USERS] == DEFAULT_USERS

    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={CONF_SOURCE: SOURCE_USER}, data=None
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_MONITORED_USERS: SELECTED_USERNAMES},
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_MONITORED_USERS] == SELECTED_USERNAMES


async def test_options_failed_getting_users(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    """Test failed getting users when unable to connect to Tautulli."""
    entry = await setup_integration(hass, aioclient_mock, invalid_auth=True)
    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "cannot_connect"


async def test_flow_import(hass: HomeAssistant):
    """Test import step."""
    with _patch_config_flow_tautulli(await _create_mocked_tautulli()), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_DATA,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == DEFAULT_NAME
        assert result["data"] == CONF_DATA


async def test_flow_import_already_configured(hass: HomeAssistant):
    """Test import step already configured."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=UNIQUE_ID, data=CONF_DATA)
    entry.add_to_hass(hass)

    with _patch_config_flow_tautulli(await _create_mocked_tautulli()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"
