"""Voice Assistant Websocket API."""
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .pipeline import DEFAULT_TIMEOUT, Pipeline, PipelineRun, TextPipelineRequest


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register the websocket API."""
    websocket_api.async_register_command(hass, websocket_run)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "voice_assistant/run",
        vol.Optional("language"): str,
        vol.Optional("pipeline"): str,
        vol.Required("intent_input"): str,
        vol.Optional("conversation_id"): vol.Any(str, None),
        vol.Optional("timeout"): vol.Any(float, int),
    }
)
@websocket_api.async_response
async def websocket_run(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Run a pipeline."""
    pipeline_id = msg.get("pipeline")
    if pipeline_id is not None:
        pipeline = hass.data[DOMAIN].get(pipeline_id)
        if pipeline is None:
            connection.send_error(
                msg["id"],
                "pipeline_not_found",
                f"Pipeline not found: {pipeline_id}",
            )
            return

    else:
        # Construct a pipeline for the required/configured language
        language = msg.get("language", hass.config.language)
        pipeline = Pipeline(
            name=language,
            language=language,
            conversation_engine=None,
            tts_engine=None,
        )

    # Run pipeline with a timeout.
    # Events are sent over the websocket connection.
    timeout = msg.get("timeout", DEFAULT_TIMEOUT)
    run_task = hass.async_create_task(
        TextPipelineRequest(
            intent_input=msg["intent_input"],
            conversation_id=msg.get("conversation_id"),
        ).execute(
            PipelineRun(
                hass,
                connection.context(msg),
                pipeline,
                event_callback=lambda event: connection.send_event(
                    msg["id"], event.as_dict()
                ),
            ),
            timeout=timeout,
        )
    )

    # Cancel pipeline if user unsubscribes
    connection.subscriptions[msg["id"]] = run_task.cancel

    connection.send_result(msg["id"])

    # Task contains a timeout
    await run_task
