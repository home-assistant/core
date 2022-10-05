"""PJLink unit testing for config flow."""
from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

from pypjlink import Projector

from homeassistant.components.pjlink.const import (
    CONF_ENCODING,
    DEFAULT_ENCODING,
    DOMAIN,
    INTEGRATION_NAME,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry


def mock_projector() -> Projector:
    """Create a mock projector."""

    # Create projector class, f is a socket file-descriptor.
    proj = Projector(f=MagicMock(), encoding="utf-8")

    proj.authenticate = Mock()

    # Metadata
    proj.get_name = Mock(return_value="PJLink Test Name")
    proj.get_product_name = Mock(return_value="PJLink Test Model")
    proj.get_manufacturer = Mock(return_value="PJLink Test Manufacturer")

    # Control methods
    proj.get_inputs = Mock(return_value=[("DIGITAL", 1), ("RGB", 1), ("VIDEO", 1)])
    proj.get_input = Mock(return_value=("DIGITAL", 1))
    proj.set_input = Mock()

    proj.get_power = Mock(return_value="off")
    proj.set_power = Mock()

    proj.get_mute = Mock(return_value=(True, False))
    proj.set_mute = Mock()

    # Status information
    proj.get_lamps = Mock(return_value=[(1376, True), (1375, True)])
    proj.get_other_info = Mock(return_value="Version 1.0")
    proj.get_errors = Mock(
        return_value={
            "fan": "ok",
            "lamp": "ok",
            "temperature": "ok",
            "cover": "ok",
            "filter": "ok",
            "other": "ok",
        }
    )

    return proj


async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test the user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == SOURCE_USER
    assert "flow_id" in result

    mock_user_input_data = {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 1234,
        CONF_NAME: "test projector",
        CONF_PASSWORD: "",
    }

    with patch.object(
        Projector, "from_address", timeout=True, return_value=mock_projector()
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=mock_user_input_data
        )

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == INTEGRATION_NAME

    assert result.get("data") == {
        CONF_ENCODING: DEFAULT_ENCODING,
        CONF_HOST: mock_user_input_data[CONF_HOST],
        CONF_PORT: mock_user_input_data[CONF_PORT],
        CONF_NAME: mock_user_input_data[CONF_NAME],
        CONF_PASSWORD: mock_user_input_data[CONF_PASSWORD],
    }

    registry = entity_registry.async_get(hass)
    entry = registry.async_get("media_player.test_projector_test_projector")

    assert entry.unique_id == entry.config_entry_id
