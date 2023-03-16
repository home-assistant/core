"""The Voice Assistant integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging
import secrets
from typing import Any

from aiohttp import web
from aiohttp.web_exceptions import HTTPBadRequest, HTTPNotFound
import voluptuous as vol

from homeassistant import core
from homeassistant.components import stt, websocket_api
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers import singleton
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_PIPELINE, DOMAIN
from .pipeline import Pipeline, PipelineRequest, PipelineResponse

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Voice Assistant integration."""
    hass.data[DOMAIN] = {
        DEFAULT_PIPELINE: Pipeline(
            name=DEFAULT_PIPELINE,
            language=hass.config.language,
            stt_engine="cloud",
            agent_id="homeassistant",
            tts_engine="cloud",
        )
    }

    hass.http.register_view(VoiceAssistantView(hass))
    websocket_api.async_register_command(hass, websocket_run)

    return True


@dataclass
class Session:
    """Pipeline session for bridging websocket/HTTP APIs."""

    pipeline: Pipeline
    connection: websocket_api.ActiveConnection
    msg: dict[str, Any]


class SessionManager:
    """Manages sessions between websocket/HTTP APIs."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Create session manager."""
        self.hass = hass
        self._sessions: dict[str, Session] = {}

    def add_session(self, session: Session) -> str:
        """Add a new session. Returns a unique session id."""
        session_id = secrets.token_urlsafe(16)
        self._sessions[session_id] = session
        return session_id

    def pop_session(self, session_id: str) -> Session | None:
        """Remove and return a session by id."""
        return self._sessions.pop(session_id, None)


@singleton.singleton("voice_assistant_session")
@core.callback
def _get_session_manager(hass: HomeAssistant) -> SessionManager:
    """Get manager for pipeline sessions."""
    return SessionManager(hass)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "voice_assistant/run",
        vol.Required("pipeline"): str,
        vol.Optional("stt_text"): str,
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

    session_manager = _get_session_manager(hass)
    session_id = session_manager.add_session(Session(pipeline, connection, msg))
    connection.subscriptions[msg["id"]] = lambda: session_manager.pop_session(
        session_id
    )

    connection.send_message(
        {"id": msg["id"], "type": "session", "session_id": session_id}
    )


class VoiceAssistantView(HomeAssistantView):
    """HTTP endpoint for posting audio data."""

    requires_auth = True
    url = "/api/voice_assistant/{pipeline_name}"
    name = "api:voice_assistant:pipeline_name"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize HTTP view."""
        self.hass = hass

    async def post(self, request: web.Request, pipeline_name: str) -> web.Response:
        """Run a pipeline using audio from HTTP request (like /api/stt)."""
        pipeline = self.hass.data[DOMAIN].get(pipeline_name)
        if pipeline is None:
            raise HTTPNotFound()

        # Get metadata
        try:
            stt_metadata = stt.metadata_from_header(request)
        except ValueError as err:
            raise HTTPBadRequest(text=str(err)) from err

        session: Session | None = None
        session_id = request.rel_url.query.get("session_id")
        if session_id is not None:
            session = _get_session_manager(self.hass).pop_session(session_id)

            if session is None:
                raise HTTPBadRequest(text=f"No session for id {session_id}")

            _LOGGER.info("Resuming session: %s", session_id)

        context = self.context(request)
        pipeline_request = PipelineRequest(
            stt_audio=request.content, stt_metadata=stt_metadata
        )

        response: PipelineResponse | None = None
        async for event in pipeline.run(self.hass, context, pipeline_request):
            if isinstance(event, PipelineResponse):
                response = event
                if session is not None:
                    session.connection.send_result(
                        session.msg["id"], response.as_dict()
                    )
            else:
                _LOGGER.debug(event)
                if session is not None:
                    session.connection.send_message(
                        {
                            "id": session.msg["id"],
                            "type": "event",
                            "event": event.as_dict(),
                        }
                    )

        return self.json(response.as_dict() if response is not None else {})
