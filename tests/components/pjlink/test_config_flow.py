"""Tests for the PJLink config flow."""

from unittest.mock import MagicMock, patch

from pypjlink import Projector

from homeassistant.components.pjlink.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry

NO_AUTH_RESPONSE = "PJLINK 0\r"


def mock_projector():
    """Mock Projector."""
    proj = Projector(f=MagicMock(), encoding="utf-8")

    proj.authenticate = MagicMock()
    proj.get_manufacturer = MagicMock(return_value="FakeManufacterer")
    proj.get_product_name = MagicMock(return_value="FakeModel")
    proj.get_name = MagicMock(return_value="FakeName")
    proj.get_inputs = MagicMock(return_value=[["DIGITAL", 1], ["VIDEO", 2]])
    proj.get_power = MagicMock(return_value="off")
    proj.get_mute = MagicMock(return_value=(True, False))
    proj.set_power = MagicMock()
    proj.set_mute = MagicMock()
    proj.set_input = MagicMock()

    return proj


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
            result["flow_id"], user_input=mock_user_input_data
        )

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == "PJLink"
    assert result.get("data") == {
        "encoding": "utf-8",
        "host": "1.2.3.4",
        "port": 1234,
        "name": "new thing",
    }

    registry = entity_registry.async_get(hass)
    entry = registry.async_get("media_player.new_thing")
    assert entry.unique_id == entry.config_entry_id
