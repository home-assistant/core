"""Additional config flow tests: frame-picker excludes configured frames."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.skylight.const import (
    CONF_DEVICE_FINGERPRINT,
    CONF_FRAME_ID,
    CONF_FRAME_NAME,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import FRAME, FRAME_ID

from tests.common import MockConfigEntry

CODE = "mock-auth-code"


async def test_pick_frame_excludes_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
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


async def test_pick_frame_all_configured_after_list(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_exchange_token: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the picker aborts when every listed frame got configured meanwhile."""
    mock_config_entry.add_to_hass(hass)

    # Two free frames so the flow shows the picker instead of auto-creating
    # an entry for the only available frame.
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

    # Simulate a concurrent flow creating an entry for the last free frame.
    MockConfigEntry(
        domain=DOMAIN,
        title="Cottage Frame",
        unique_id="skylight_frame_frame-2",
        data={
            CONF_FRAME_ID: "frame-2",
            CONF_FRAME_NAME: "Cottage Frame",
            CONF_TOKEN: {
                CONF_ACCESS_TOKEN: "a",
                CONF_REFRESH_TOKEN: "r",
                CONF_DEVICE_FINGERPRINT: "f",
            },
        },
    ).add_to_hass(hass)

    # frame-3 is still free, so the submitted frame-2 is no longer in the
    # picker's available list: the concurrent-configuration abort fires.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"frame_id": "frame-2"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "all_frames_configured"


async def test_pick_frame_shows_abort_when_nothing_free(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_exchange_token: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test re-opening the picker with every listed frame already configured."""
    mock_config_entry.add_to_hass(hass)

    # Two free frames so the flow shows the picker instead of auto-creating.
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

    # Concurrent flows configured both free frames while the picker was
    # open; re-rendering the step must abort instead of showing options.
    for frame_id, name in (("frame-2", "Cottage Frame"), ("frame-3", "Studio Frame")):
        MockConfigEntry(
            domain=DOMAIN,
            title=name,
            unique_id=f"skylight_frame_{frame_id}",
            data={
                CONF_FRAME_ID: frame_id,
                CONF_FRAME_NAME: name,
                CONF_TOKEN: {
                    CONF_ACCESS_TOKEN: "a",
                    CONF_REFRESH_TOKEN: "r",
                    CONF_DEVICE_FINGERPRINT: "f",
                },
            },
        ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], None)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "all_frames_configured"
