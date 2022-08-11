"""Tests for the PJLink config flow."""

from unittest.mock import MagicMock, patch

from pypjlink import Projector

from homeassistant.components.pjlink.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

NO_AUTH_RESPONSE = "PJLINK 0\r"


def mock_projector():
    """Mock Projector."""
    mock_proj = MagicMock()

    mock_proj.get_manufacturer.return_value = "FakeManufacterer"
    mock_proj.get_model.return_value = "FakeModel"
    mock_proj.get_product_name.return_value = ""
    mock_proj.get_name.return_value = ""
    mock_proj.get_inputs.return_value = ""
    mock_proj.get_power.return_value = ""
    mock_proj.get_mute.return_value = " "

    mock_proj.set_power.return_value = " "
    mock_proj.set_mute.return_value = " "
    mock_proj.set_input.return_value = " "


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
        "name": "new thing",
    }

    with patch.object(
        Projector, "from_address", timeout=True, return_value=mock_projector()
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], mock_user_input_data
        )

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == "PJLink"
    assert result.get("data") == {
        "encoding": "utf-8",
        "unique_id": "pjlink-1.2.3.4",
        "host": "1.2.3.4",
        "port": 1234,
        "name": "new thing",
    }
