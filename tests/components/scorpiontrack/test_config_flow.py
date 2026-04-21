"""Test the ScorpionTrack config flow."""

from __future__ import annotations

from unittest.mock import patch

from pyscorpiontrack import (
    ScorpionTrackConnectionError,
    ScorpionTrackInvalidTokenError,
    ScorpionTrackShareUnavailableError,
)
import pytest

from homeassistant.components.scorpiontrack.const import CONF_SHARE_TOKEN, DOMAIN
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
