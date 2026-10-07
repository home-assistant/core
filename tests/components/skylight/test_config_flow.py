"""Test the Skylight config flow."""

from unittest.mock import AsyncMock, patch

from skylight_api import SkylightAuthError

from homeassistant import config_entries
from homeassistant.components.skylight.const import (
    CONF_DEVICE_FINGERPRINT,
    CONF_FRAME_ID,
    CONF_FRAME_NAME,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import FRAME, FRAME_ID, FRAME_NAME

from tests.common import MockConfigEntry

CODE = "mock-auth-code"


async def test_full_flow_single_frame(
    hass: HomeAssistant,
    mock_exchange_token: AsyncMock,
    mock_get_frames: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full user flow when the account has exactly one frame."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "authorize_url" in result["description_placeholders"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"code": CODE}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == FRAME_NAME
    assert result["data"][CONF_FRAME_ID] == FRAME_ID
    assert result["data"][CONF_FRAME_NAME] == FRAME_NAME
    token = result["data"][CONF_TOKEN]
    assert token[CONF_ACCESS_TOKEN] == "mock-access-token"
    assert token[CONF_REFRESH_TOKEN] == "mock-refresh-token"
    assert len(token[CONF_DEVICE_FINGERPRINT]) == 32
    assert len(mock_exchange_token.mock_calls) == 1
    assert mock_get_frames.await_count == 1

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == f"skylight_frame_{FRAME_ID}"


async def test_full_flow_pick_frame(
    hass: HomeAssistant,
    mock_exchange_token: AsyncMock,
    mock_get_frames_two: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the flow when the account has multiple frames."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"code": CODE}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_frame"

    # Pick the second frame.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"frame_id": "frame-2"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Cottage Frame"
    assert result["data"][CONF_FRAME_ID] == "frame-2"


async def test_flow_invalid_code(
    hass: HomeAssistant,
    mock_exchange_token: AsyncMock,
    mock_get_frames: AsyncMock,
) -> None:
    """Test submitting a pasted value without any code in it."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"code": ""}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"code": "invalid_code"}
    mock_exchange_token.assert_not_awaited()


async def test_flow_full_url_pasted(
    hass: HomeAssistant,
    mock_exchange_token: AsyncMock,
    mock_get_frames: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test pasting the whole callback URL instead of the bare code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"code": f"https://ourskylight.com/welcome?code={CODE}&state=x"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_code_exchange_auth_error(
    hass: HomeAssistant,
    mock_get_frames: AsyncMock,
) -> None:
    """Test an auth failure during the code exchange."""
    with patch(
        "homeassistant.components.skylight.config_flow.exchange_authorization_code",
        side_effect=SkylightAuthError("bad code"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": CODE}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_flow_no_frames(
    hass: HomeAssistant,
    mock_exchange_token: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test aborting when the account has no frames."""
    with patch("skylight_api.SkylightAPI.get_frames", return_value=[]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": CODE}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_frames"


async def test_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_exchange_token: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test aborting when the frame is already set up."""
    mock_config_entry.add_to_hass(hass)

    with patch("skylight_api.SkylightAPI.get_frames", return_value=[FRAME]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": CODE}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "all_frames_configured"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_exchange_token: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the reauth flow updates tokens."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"code": CODE}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    token = mock_config_entry.data[CONF_TOKEN]
    assert token[CONF_ACCESS_TOKEN] == "mock-access-token"
    assert token[CONF_REFRESH_TOKEN] == "mock-refresh-token"
    assert mock_config_entry.state is ConfigEntryState.LOADED
