"""Test the Dexcom config flow."""

from unittest.mock import patch

from pydexcom import AccountError, SessionError

from homeassistant import config_entries
from homeassistant.components.dexcom.const import DOMAIN, MG_DL, MMOL_L
from homeassistant.const import CONF_UNIT_OF_MEASUREMENT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import CONFIG

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.dexcom.config_flow.Dexcom.create_session",
            return_value="test_session_id",
        ),
        patch(
            "homeassistant.components.dexcom.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == CONFIG[CONF_USERNAME]
    assert result2["data"] == CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_account_error(hass: HomeAssistant) -> None:
    """Test we handle account error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.dexcom.config_flow.Dexcom",
        side_effect=AccountError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_session_error(hass: HomeAssistant) -> None:
    """Test we handle session error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.dexcom.config_flow.Dexcom",
        side_effect=SessionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.dexcom.config_flow.Dexcom",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            CONFIG,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_option_flow_default(hass: HomeAssistant) -> None:
    """Test config flow options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG,
        options=None,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        CONF_UNIT_OF_MEASUREMENT: MG_DL,
    }


async def test_option_flow(hass: HomeAssistant) -> None:
    """Test config flow options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG,
        options={CONF_UNIT_OF_MEASUREMENT: MG_DL},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_UNIT_OF_MEASUREMENT: MMOL_L},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_UNIT_OF_MEASUREMENT: MMOL_L,
    }
