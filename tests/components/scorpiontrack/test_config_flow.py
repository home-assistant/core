"""Test the ScorpionTrack config flow."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

from pyscorpiontrack import (
    ScorpionTrackConnectionError,
    ScorpionTrackInvalidTokenError,
    ScorpionTrackShare,
    ScorpionTrackShareUnavailableError,
)
import pytest

from homeassistant.components.scorpiontrack.const import (
    CONF_SHARE_TOKEN,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType

from tests.common import MockConfigEntry


async def _async_start_user_flow(hass: HomeAssistant) -> FlowResult:
    """Start the user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    return result


async def test_user_flow_creates_entry(
    hass: HomeAssistant,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """A valid token should create a config entry."""
    result = await _async_start_user_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SHARE_TOKEN: (
                "  https://app.scorpiontrack.com/shared/location"
                "?token=canonical-token  "
            )
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Family Cars"
    assert result["data"] == {CONF_SHARE_TOKEN: "canonical-token"}
    assert result["result"].unique_id == "101"
    mock_scorpiontrack_client.async_get_share.assert_awaited()


async def test_user_flow_uses_vehicle_display_name_without_share_title(
    hass: HomeAssistant,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """The config entry title should fall back to the first vehicle display name."""
    share = replace(mock_share, title="")
    mock_scorpiontrack_client.async_get_share.return_value = share

    result = await _async_start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SHARE_TOKEN: "canonical-token"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == share.vehicles[0].display_name
    assert result["result"].unique_id == "101"


async def test_user_flow_uses_default_name_without_title_or_vehicles(
    hass: HomeAssistant,
    mock_share: ScorpionTrackShare,
    mock_scorpiontrack_client: AsyncMock,
) -> None:
    """The config entry title should use the default name when nothing descriptive exists."""
    share = replace(mock_share, title="", vehicles=())
    mock_scorpiontrack_client.async_get_share.return_value = share

    result = await _async_start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SHARE_TOKEN: "canonical-token"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["result"].unique_id == "101"


async def test_user_flow_aborts_for_existing_share(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The same share should not be configured twice."""
    mock_config_entry.add_to_hass(hass)

    result = await _async_start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SHARE_TOKEN: "canonical-token"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (
            ScorpionTrackConnectionError("Connection failed"),
            "cannot_connect",
        ),
        (ScorpionTrackInvalidTokenError("Invalid token"), "invalid_token"),
        (
            ScorpionTrackShareUnavailableError("Share expired"),
            "share_unavailable",
        ),
        (Exception("Unexpected error"), "unknown"),
    ],
)
async def test_user_flow_shows_validation_errors(
    hass: HomeAssistant,
    mock_scorpiontrack_client: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Validation errors should surface the correct base error."""
    mock_scorpiontrack_client.async_get_share.side_effect = side_effect

    result = await _async_start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SHARE_TOKEN: "canonical-token"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}


async def test_user_flow_maps_malformed_input_to_invalid_token(
    hass: HomeAssistant,
) -> None:
    """Malformed pasted values should show the invalid-token form error."""
    with patch(
        "homeassistant.components.scorpiontrack.config_flow.ScorpionTrackClient.extract_token",
        side_effect=ValueError("Could not parse share link"),
    ):
        result = await _async_start_user_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SHARE_TOKEN: "not a share"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_token"}


async def test_user_flow_recovers_after_invalid_token(
    hass: HomeAssistant,
) -> None:
    """The user flow should recover after an invalid token error."""
    result = await _async_start_user_flow(hass)

    with patch(
        "homeassistant.components.scorpiontrack.config_flow.ScorpionTrackClient.extract_token",
        side_effect=ScorpionTrackInvalidTokenError("Invalid token"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SHARE_TOKEN: "not a share"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_token"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SHARE_TOKEN: "canonical-token"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_SHARE_TOKEN: "canonical-token"}
    assert result["result"].unique_id == "101"
