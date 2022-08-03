"""Tests for the PJLink config flow."""
# from unittest.mock import patch

from homeassistant.components.pjlink.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

# from tests.common import MockConfigEntry


async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == SOURCE_USER
    assert "flow_id" in result

    mock_user_input_data = {
        "host": "1.2.3.4",
        "port": 1234,
        "password": "shh",
        "name": "new thing",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], mock_user_input_data
    )

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == "PJLink"
    assert result.get("data") == mock_user_input_data
