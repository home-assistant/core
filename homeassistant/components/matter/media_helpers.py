"""Helpers for Matter media devices."""

from typing import Any

from chip.clusters import Objects as clusters

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

PlaybackStatus = clusters.MediaPlayback.Enums.StatusEnum

# Translation keys for the PlaybackResponse statuses that are not success
PLAYBACK_STATUS_ERRORS: dict[int, str] = {
    PlaybackStatus.kInvalidStateForCommand: "media_playback_invalid_state",
    PlaybackStatus.kNotAllowed: "media_playback_not_allowed",
    PlaybackStatus.kNotActive: "media_playback_not_active",
    PlaybackStatus.kSpeedOutOfRange: "media_playback_speed_out_of_range",
    PlaybackStatus.kSeekOutOfRange: "media_playback_seek_out_of_range",
}


def raise_for_status(
    response: dict[str, Any],
    status_errors: dict[int, str],
    unknown_error: str,
    placeholders: dict[str, str] | None = None,
) -> None:
    """Raise the translated error for a command response that is not a success.

    Status 0 means success in every Matter media cluster with a status response.
    """
    status = response["status"]
    if status == 0:
        return
    if (translation_key := status_errors.get(status)) is None:
        translation_key = unknown_error
        placeholders = {**(placeholders or {}), "status": str(status)}
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key=translation_key,
        translation_placeholders=placeholders,
    )


def raise_for_playback_status(response: dict[str, Any]) -> None:
    """Raise if a Media Playback PlaybackResponse does not report success."""
    raise_for_status(response, PLAYBACK_STATUS_ERRORS, "media_playback_failed")
