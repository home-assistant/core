"""Test the laundrify config flow."""
from unittest.mock import patch

from laundrify_aio import exceptions

from homeassistant.components.laundrify.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CODE, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from . import (
    _patch_laundrify_exchange_code,
    _patch_laundrify_get_account_id,
    _patch_laundrify_get_machines,
    _patch_laundrify_validate_token,
    create_entry,
)
from .const import VALID_ACCESS_TOKEN, VALID_AUTH_CODE, VALID_USER_INPUT


def _patch_setup_entry():
    return patch("homeassistant.components.laundrify.async_setup_entry")


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    with _patch_laundrify_exchange_code(), _patch_laundrify_get_account_id(), _patch_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["errors"] is None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=VALID_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DOMAIN
    assert result["data"] == {
        CONF_ACCESS_TOKEN: VALID_ACCESS_TOKEN,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_format(hass: HomeAssistant) -> None:
    """Test we handle invalid format."""
    with _patch_laundrify_exchange_code() as laundrify_mock:
        laundrify_mock.side_effect = exceptions.InvalidFormat
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
            data={CONF_CODE: "invalidFormat"},
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {CONF_CODE: "invalid_format"}


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    with _patch_laundrify_exchange_code() as laundrify_mock:
        laundrify_mock.side_effect = exceptions.UnknownAuthCode
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
            data=VALID_USER_INPUT,
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {CONF_CODE: "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant):
    """Test we handle cannot connect error."""
    with _patch_laundrify_exchange_code() as laundrify_mock:
        laundrify_mock.side_effect = exceptions.ApiConnectionException
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
            data=VALID_USER_INPUT,
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_unkown_exception(hass: HomeAssistant):
    """Test we handle all other errors."""
    with _patch_laundrify_exchange_code() as laundrify_mock:
        laundrify_mock.side_effect = Exception
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_USER},
            data=VALID_USER_INPUT,
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "unknown"}


async def test_step_reauth(hass: HomeAssistant) -> None:
    """Test the reauth form is shown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_REAUTH}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_FORM


async def test_integration_already_exists(hass: HomeAssistant):
    """Test we only allow a single config flow."""
    create_entry(hass)
    with _patch_laundrify_exchange_code(), _patch_laundrify_get_account_id():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_CODE: VALID_AUTH_CODE,
            },
        )

        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


async def test_setup_entry_api_unauthorized(hass: HomeAssistant):
    """Test that ConfigEntryAuthFailed is thrown when authentication fails."""
    with _patch_setup_entry(), _patch_laundrify_get_machines() as laundrify_mock:
        laundrify_mock.side_effect = exceptions.UnauthorizedException
        config_entry = create_entry(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state == ConfigEntryState.SETUP_ERROR
    assert not hass.data.get(DOMAIN)


async def test_setup_entry_successful(hass: HomeAssistant):
    """Test entry can be setup successfully."""
    with _patch_laundrify_exchange_code(), _patch_laundrify_validate_token(), _patch_laundrify_get_machines():
        config_entry = create_entry(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state == ConfigEntryState.LOADED


async def test_setup_entry_unload(hass: HomeAssistant):
    """Test unloading the laundrify entry."""
    with _patch_laundrify_exchange_code(), _patch_laundrify_validate_token(), _patch_laundrify_get_machines():
        config_entry = create_entry(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.config_entries.async_unload(config_entry.entry_id)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state == ConfigEntryState.NOT_LOADED
