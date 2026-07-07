"""Control recorder entity options."""

import dataclasses
from enum import StrEnum
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from .util import get_instance


def is_entity_recorded(hass: HomeAssistant, entity_id: str) -> bool:
    """Check if an entity is being recorded.

    Async friendly.
    """
    instance = get_instance(hass)
    return instance.entity_filter is None or instance.entity_filter(entity_id)


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the recorder entity options."""
    websocket_api.async_register_command(hass, ws_get_entity_options)


class EntityRecordingDisabler(StrEnum):
    """What disabled recording of an entity."""

    USER = "user"


@dataclasses.dataclass(frozen=True)
class RecorderEntityOptions:
    """Recorder options for an entity."""

    recording_disabled_by: EntityRecordingDisabler | None = None

    def to_json(self) -> dict[str, Any]:
        """Return a JSON serializable representation for storage."""
        return {
            "recording_disabled_by": self.recording_disabled_by,
        }


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/entity_options/get",
        vol.Required("entity_id"): cv.strict_entity_id,
    }
)
@callback
def ws_get_entity_options(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Get recorder settings for a single entity."""
    entity_id: str = msg["entity_id"]
    recording_disabled = (
        None if is_entity_recorded(hass, entity_id) else EntityRecordingDisabler.USER
    )

    options = RecorderEntityOptions(recording_disabled_by=recording_disabled)
    connection.send_result(msg["id"], options.to_json())
