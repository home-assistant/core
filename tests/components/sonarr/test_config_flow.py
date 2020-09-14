"""Test the Sonarr config flow."""
from homeassistant.components.sonarr.const import (
    CONF_UPCOMING_DAYS,
    CONF_WANTED_MAX_ITEMS,
    DEFAULT_UPCOMING_DAYS,
    DEFAULT_WANTED_MAX_ITEMS,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_SOURCE, CONF_VERIFY_SSL
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)
from homeassistant.helpers.typing import HomeAssistantType

from tests.async_mock import patch
from tests.components.sonarr import (
    HOST,
    MOCK_USER_INPUT,
    _patch_async_setup,
    _patch_async_setup_entry,
    mock_connection,
    mock_connection_error,
    mock_connection_invalid_auth,
    setup_integration,
)
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_show_user_form(hass: HomeAssistantType) -> None:
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] == RESULT_TYPE_FORM


async def test_cannot_connect(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show user form on connection error."""
    mock_connection_error(aioclient_mock)

    user_input = MOCK_USER_INPUT.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=user_input,
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_invalid_auth(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show user form on invalid auth."""
    mock_connection_invalid_auth(aioclient_mock)

    user_input = MOCK_USER_INPUT.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=user_input,
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_unknown_error(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we show user form on unknown error."""
    user_input = MOCK_USER_INPUT.copy()
    with patch(
        "homeassistant.components.sonarr.config_flow.Sonarr.update",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
            data=user_input,
        )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "unknown"


async def test_full_import_flow_implementation(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the full manual user flow from start to finish."""
    mock_connection(aioclient_mock)

    user_input = MOCK_USER_INPUT.copy()

    with _patch_async_setup(), _patch_async_setup_entry():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_IMPORT},
            data=user_input,
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST

    assert result["data"]
    assert result["data"][CONF_HOST] == HOST


async def test_full_user_flow_implementation(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the full manual user flow from start to finish."""
    mock_connection(aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    user_input = MOCK_USER_INPUT.copy()

    with _patch_async_setup(), _patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST

    assert result["data"]
    assert result["data"][CONF_HOST] == HOST


async def test_full_user_flow_advanced_options(
    hass: HomeAssistantType, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the full manual user flow with advanced options."""
    mock_connection(aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER, "show_advanced_options": True}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    user_input = {
        **MOCK_USER_INPUT,
        CONF_VERIFY_SSL: True,
    }

    with _patch_async_setup(), _patch_async_setup_entry():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST

    assert result["data"]
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_VERIFY_SSL]


async def test_options_flow(hass, aioclient_mock: AiohttpClientMocker):
    """Test updating options."""
    entry = await setup_integration(hass, aioclient_mock, skip_entry_setup=True)
    assert entry.options[CONF_UPCOMING_DAYS] == DEFAULT_UPCOMING_DAYS
    assert entry.options[CONF_WANTED_MAX_ITEMS] == DEFAULT_WANTED_MAX_ITEMS

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    with _patch_async_setup(), _patch_async_setup_entry():
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_UPCOMING_DAYS: 2, CONF_WANTED_MAX_ITEMS: 100},
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_UPCOMING_DAYS] == 2
    assert result["data"][CONF_WANTED_MAX_ITEMS] == 100
