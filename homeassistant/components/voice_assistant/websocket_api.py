"""Voice Assistant Websocket API."""
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .pipeline import DEFAULT_TIMEOUT, PipelineRequest, PipelineStage


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register the websocket API."""
    websocket_api.async_register_command(hass, websocket_run)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "voice_assistant/run",
        vol.Optional("pipeline", default="default"): str,
        vol.Required("intent_input"): str,
        vol.Optional("conversation_id"): vol.Any(str, None),
        vol.Optional("timeout"): vol.Any(float, int),
        vol.Optional("start_stage"): str,
        vol.Optional("stop_stage"): str,
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

    start_stage = PipelineStage(msg["start_stage"]) if "start_stage" in msg else None
    stop_stage = PipelineStage(msg["stop_stage"]) if "stop_stage" in msg else None

    # Run pipeline with a timeout.
    # Events are sent over the websocket connection.
    timeout = msg.get("timeout", DEFAULT_TIMEOUT)
    run_task = hass.async_create_task(
        pipeline.run(
            hass,
            connection.context(msg),
            request=PipelineRequest(
                intent_input=msg["intent_input"],
                conversation_id=msg.get("conversation_id"),
            ),
            event_callback=lambda event: connection.send_event(
                msg["id"], event.as_dict()
            ),
            start_stage=start_stage,
            stop_stage=stop_stage,
            timeout=timeout,
        )
    )

    # Cancel pipeline if user unsubscribes
    connection.subscriptions[msg["id"]] = run_task.cancel

    connection.send_result(msg["id"])

    # Task contains a timeout
    await run_task
