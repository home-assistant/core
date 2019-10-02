"""Google Report State implementation."""
from uuid import uuid4
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import MATCH_ALL

from .helpers import AbstractConfig, GoogleEntity


@callback
def async_enable_report_state(hass: HomeAssistant, google_config: AbstractConfig):
    """Enable state reporting."""

    async def async_entity_state_listener(changed_entity, old_state, new_state):
        if not new_state:
            return

        if not google_config.should_expose(new_state):
            return

        entity = GoogleEntity(hass, google_config, new_state)

        if not entity.is_supported():
            return

        await google_config.async_report_state(
            {
                "requestId": uuid4().hex,
                "agentUserId": google_config.agent_user_id,
                "payload": {
                    "devices": {"states": {changed_entity: entity.query_serialize()}}
                },
            }
        )

    return hass.helpers.event.async_track_state_change(
        MATCH_ALL, async_entity_state_listener
    )
