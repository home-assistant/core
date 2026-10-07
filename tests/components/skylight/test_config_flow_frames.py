"""Additional config flow tests: frame-picker excludes configured frames."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.skylight.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import FRAME, FRAME_ID

CODE = "mock-auth-code"


async def test_pick_frame_excludes_configured(
    hass: HomeAssistant,
    mock_config_entry,
    mock_exchange_token: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the picker only offers frames that are not configured yet."""
    mock_config_entry.add_to_hass(hass)

    frames = [
        FRAME,
        {"id": "frame-2", "name": "Cottage Frame"},
        {"id": "frame-3", "name": "Studio Frame"},
    ]
    with patch("skylight_api.SkylightAPI.get_frames", return_value=frames):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": CODE}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_frame"
    schema = result["data_schema"].schema
    options = [option["value"] for option in schema["frame_id"].config["options"]]
    assert options == ["frame-2", "frame-3"]
    assert FRAME_ID not in options

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"frame_id": "frame-2"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["frame_id"] == "frame-2"
