"""Control which entities are recorded."""

import dataclasses
from enum import StrEnum
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback


async def async_setup(hass: HomeAssistant) -> None:
    """Set up the recorded entities."""
    websocket_api.async_register_command(hass, ws_get_recorded_entity)


class EntityRecordingDisabler(StrEnum):
    """What disabled recording of an entity."""

    USER = "user"


@dataclasses.dataclass(frozen=True)
class RecordedEntity:
    """A recorded entity without a unique_id."""

    recording_disabled_by: EntityRecordingDisabler | None = None

    def to_json(self) -> dict[str, Any]:
        """Return a JSON serializable representation for storage."""
        return {
            "recording_disabled_by": self.recording_disabled_by,
        }


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "recorder/recorded_entities/get",
        vol.Required("entity_id"): str,
    }
)
def ws_get_recorded_entity(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Get recorder settings for a single entity."""
    from . import is_entity_recorded  # noqa: PLC0415

    entity_id: str = msg["entity_id"]
    recording_disabled = (
        None if is_entity_recorded(hass, entity_id) else EntityRecordingDisabler.USER
    )

    options = RecordedEntity(recording_disabled_by=recording_disabled)
    connection.send_result(msg["id"], options.to_json())
