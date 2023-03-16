"""Voice Assistant Websocket API."""
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .pipeline import PipelineRequest


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register the websocket API."""
    websocket_api.async_register_command(hass, websocket_run)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "voice_assistant/run",
        vol.Optional("pipeline", default="default"): str,
        vol.Required("stt_text"): str,
        vol.Optional("conversation_id"): vol.Any(str, None),
    }
)
@websocket_api.async_response
async def websocket_run(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Run a pipeline."""
    pipeline_id = msg["pipeline"]
    pipeline = hass.data[DOMAIN].get(pipeline_id)
    if pipeline is None:
        connection.send_error(
            msg["id"], "pipeline_not_found", f"Pipeline not found: {pipeline_id}"
        )
        return

    connection.subscriptions[msg["id"]] = lambda: None
    connection.send_result(msg["id"])

    async for event in pipeline.run(
        hass,
        connection.context(msg),
        request=PipelineRequest(
            stt_audio=None,
            stt_metadata=None,
            stt_text=msg["stt_text"],
            conversation_id=msg.get("conversation_id"),
        ),
    ):
        connection.send_event(msg["id"], event.as_dict())
