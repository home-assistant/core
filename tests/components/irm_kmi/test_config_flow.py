"""Tests for the IRM KMI config flow."""

from unittest.mock import MagicMock

from homeassistant.components.irm_kmi.const import CONF_LANGUAGE_OVERRIDE, DOMAIN
from homeassistant.components.zone import ENTITY_ID_HOME
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_get_forecast_in_benelux: MagicMock,
) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ZONE: ENTITY_ID_HOME},
    )
    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "test home"
    assert result2.get("data") == {CONF_ZONE: ENTITY_ID_HOME}


async def test_config_flow_out_benelux_zone(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_get_forecast_out_benelux: MagicMock,
) -> None:
    """Test configuration flow with a zone outside of Benelux."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ZONE: ENTITY_ID_HOME},
    )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "user"
    assert CONF_ZONE in result2.get("errors")


async def test_config_flow_with_api_error(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_get_forecast_api_error: MagicMock,
) -> None:
    """Test when API returns an error during the configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ZONE: ENTITY_ID_HOME},
    )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "user"
    assert "base" in result2.get("errors")


async def test_config_flow_unknown_zone(hass: HomeAssistant) -> None:
    """Test when the selected zone in the configuration flow does not exist."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ZONE: "zone.what"},
    )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "user"
    assert CONF_ZONE in result2.get("errors")


async def test_option_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test when the users changes options with the option flow."""
    mock_config_entry.add_to_hass(hass)

    assert not mock_config_entry.options

    result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id, data=None
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_LANGUAGE_OVERRIDE: "none"}
