"""Tests for the Open-Meteo config flow."""

from unittest.mock import MagicMock

from homeassistant.components.open_meteo.const import DOMAIN
from homeassistant.components.zone import ENTITY_ID_HOME
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ZONE: ENTITY_ID_HOME},
    )

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "test home"
    assert result2.get("data") == {CONF_ZONE: ENTITY_ID_HOME}
