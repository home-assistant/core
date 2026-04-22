"""Test the ScorpionTrack config flow."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import AsyncMock, patch

from pyscorpiontrack import (
    ScorpionTrackClient,
    ScorpionTrackConnectionError,
    ScorpionTrackInvalidTokenError,
    ScorpionTrackShareUnavailableError,
)
import pytest

from homeassistant.components.scorpiontrack.config_flow import _async_validate_input
from homeassistant.components.scorpiontrack.const import (
    CONF_SHARE_TOKEN,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

VALIDATION_INFO = {
    "token": "canonical-token",
    "title": "Family Cars",
    "unique_id": "101",
}


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """A valid token should create a config entry."""
    with patch(
        "homeassistant.components.scorpiontrack.config_flow._async_validate_input",
        return_value=VALIDATION_INFO,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_SHARE_TOKEN: "https://app.scorpiontrack.com/shared/location?token=abc"
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Family Cars"
    assert result["data"] == {CONF_SHARE_TOKEN: "canonical-token"}


async def test_validate_input_strips_whitespace_and_uses_share_title(
    hass: HomeAssistant,
    mock_share,
) -> None:
    """Validation should strip pasted whitespace and prefer the share title."""
    with patch(
        "homeassistant.components.scorpiontrack.config_flow.ScorpionTrackClient",
    ) as mock_client:
        mock_client.extract_token.side_effect = ScorpionTrackClient.extract_token
        mock_client.return_value.async_get_share = AsyncMock(return_value=mock_share)

        info = await _async_validate_input(
            hass,
            {CONF_SHARE_TOKEN: "  canonical-token  \n"},
        )

    assert mock_client.call_args.kwargs["token"] == "canonical-token"
    assert info == VALIDATION_INFO


async def test_validate_input_extracts_token_from_share_url(
    hass: HomeAssistant,
    mock_share,
) -> None:
    """Validation should accept the pasted ScorpionTrack share URL format."""
    with patch(
        "homeassistant.components.scorpiontrack.config_flow.ScorpionTrackClient",
    ) as mock_client:
        mock_client.extract_token.side_effect = ScorpionTrackClient.extract_token
        mock_client.return_value.async_get_share = AsyncMock(return_value=mock_share)

        info = await _async_validate_input(
            hass,
            {
                CONF_SHARE_TOKEN: (
                    "  https://app.scorpiontrack.com/shared/location"
                    "?token=canonical-token  "
                )
            },
        )

    assert mock_client.call_args.kwargs["token"] == "canonical-token"
    assert info == VALIDATION_INFO


async def test_validate_input_uses_vehicle_display_name_without_share_title(
    hass: HomeAssistant,
    mock_share,
) -> None:
    """Validation should fall back to the first vehicle display name."""
    share = replace(mock_share, title="")
    with patch(
        "homeassistant.components.scorpiontrack.config_flow.ScorpionTrackClient",
    ) as mock_client:
        mock_client.extract_token.side_effect = ScorpionTrackClient.extract_token
        mock_client.return_value.async_get_share = AsyncMock(return_value=share)

        info = await _async_validate_input(
            hass,
            {CONF_SHARE_TOKEN: "canonical-token"},
        )

    assert info["title"] == share.vehicles[0].display_name


async def test_validate_input_uses_default_name_without_title_or_vehicles(
    hass: HomeAssistant,
    mock_share,
) -> None:
    """Validation should use the default name when nothing descriptive exists."""
    share = replace(mock_share, title="", vehicles=())
    with patch(
        "homeassistant.components.scorpiontrack.config_flow.ScorpionTrackClient",
    ) as mock_client:
        mock_client.extract_token.side_effect = ScorpionTrackClient.extract_token
        mock_client.return_value.async_get_share = AsyncMock(return_value=share)

        info = await _async_validate_input(
            hass,
            {CONF_SHARE_TOKEN: "canonical-token"},
        )

    assert info["title"] == DEFAULT_NAME


async def test_user_flow_aborts_for_existing_share(hass: HomeAssistant) -> None:
    """The same share should not be configured twice."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Family Cars",
        unique_id="101",
        data={CONF_SHARE_TOKEN: "existing-token"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.scorpiontrack.config_flow._async_validate_input",
        return_value=VALIDATION_INFO,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_SHARE_TOKEN: "new-token"},
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
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Validation errors should surface the correct base error."""
    with patch(
        "homeassistant.components.scorpiontrack.config_flow._async_validate_input",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_SHARE_TOKEN: "canonical-token"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}
