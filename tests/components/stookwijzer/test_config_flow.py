"""Tests for the Stookwijzer config flow."""

from unittest.mock import patch

from homeassistant.components.stookwijzer.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert "flow_id" in result

    with patch(
        "homeassistant.components.stookwijzer.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_LOCATION: {
                    CONF_LATITUDE: 1.0,
                    CONF_LONGITUDE: 1.1,
                }
            },
        )

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("data") == {
        "location": {
            "latitude": 1.0,
            "longitude": 1.1,
        },
    }

    assert len(mock_setup_entry.mock_calls) == 1
