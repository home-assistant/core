"""Test the Flick Electric config flow."""
from unittest.mock import patch

from pyflick.authentication import AuthException

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.flick_electric.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CONF = {CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"}


async def _flow_submit(hass):
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=CONF,
    )


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.flick_electric.config_flow.SimpleFlickAuth.async_get_access_token",
        return_value="123456789abcdef",
    ), patch(
        "homeassistant.components.flick_electric.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONF,
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Flick Electric: test-username"
    assert result2["data"] == CONF
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_duplicate_login(hass: HomeAssistant) -> None:
    """Test uniqueness of username."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF,
        title="Flick Electric: test-username",
        unique_id="flick_electric_test-username",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.flick_electric.config_flow.SimpleFlickAuth.async_get_access_token",
        return_value="123456789abcdef",
    ):
        result = await _flow_submit(hass)

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    with patch(
        "homeassistant.components.flick_electric.config_flow.SimpleFlickAuth.async_get_access_token",
        side_effect=AuthException,
    ):
        result = await _flow_submit(hass)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    with patch(
        "homeassistant.components.flick_electric.config_flow.SimpleFlickAuth.async_get_access_token",
        side_effect=TimeoutError,
    ):
        result = await _flow_submit(hass)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_generic_exception(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    with patch(
        "homeassistant.components.flick_electric.config_flow.SimpleFlickAuth.async_get_access_token",
        side_effect=Exception,
    ):
        result = await _flow_submit(hass)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
