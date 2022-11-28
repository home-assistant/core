"""Test the laundrify config flow."""

from laundrify_aio import exceptions

from homeassistant.components.laundrify.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CODE, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import create_entry
from .const import VALID_ACCESS_TOKEN, VALID_AUTH_CODE, VALID_USER_INPUT


async def test_form(hass: HomeAssistant, laundrify_setup_entry) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=VALID_USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == DOMAIN
    assert result["data"] == {
        CONF_ACCESS_TOKEN: VALID_ACCESS_TOKEN,
    }
    assert len(laundrify_setup_entry.mock_calls) == 1


async def test_form_invalid_format(
    hass: HomeAssistant, laundrify_exchange_code
) -> None:
    """Test we handle invalid format."""
    laundrify_exchange_code.side_effect = exceptions.InvalidFormat

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data={CONF_CODE: "invalidFormat"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_CODE: "invalid_format"}


async def test_form_invalid_auth(hass: HomeAssistant, laundrify_exchange_code) -> None:
    """Test we handle invalid auth."""
    laundrify_exchange_code.side_effect = exceptions.UnknownAuthCode
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=VALID_USER_INPUT,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_CODE: "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant, laundrify_exchange_code):
    """Test we handle cannot connect error."""
    laundrify_exchange_code.side_effect = exceptions.ApiConnectionException
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=VALID_USER_INPUT,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_unkown_exception(hass: HomeAssistant, laundrify_exchange_code):
    """Test we handle all other errors."""
    laundrify_exchange_code.side_effect = Exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=VALID_USER_INPUT,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_step_reauth(hass: HomeAssistant) -> None:
    """Test the reauth form is shown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_REAUTH}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM


async def test_integration_already_exists(hass: HomeAssistant):
    """Test we only allow a single config flow."""
    create_entry(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_CODE: VALID_AUTH_CODE,
        },
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
