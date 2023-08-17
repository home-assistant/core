"""Test for the Fast.com config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.fastdotcom.const import DOMAIN
from homeassistant.components.fastdotcom.coordinator import (
    FastdotcomDataUpdateCoordindator,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_user_form(hass: HomeAssistant) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.fastdotcom.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Fast.com"
    assert result["data"] == {}
    assert result["options"] == {}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test import flow."""
    coordinator = FastdotcomDataUpdateCoordindator(hass)
    with patch(
        "homeassistant.components.fastdotcom.coordinator.fast_com",
        return_value={"download": "50"},
    ), patch("homeassistant.components.fastdotcom.sensor.SpeedtestSensor"):
        await coordinator.async_refresh()
        assert coordinator.data == {"download": "50"}
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={},
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Fast.com"
        assert result["data"] == {}
        assert result["options"] == {}
