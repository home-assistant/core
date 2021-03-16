"""Describe logbook events."""
from homeassistant.components.logbook import LazyEventPartialState
from homeassistant.const import ATTR_ENTITY_ID, ATTR_NAME, CONF_ID
from homeassistant.core import HomeAssistant, callback

from . import ATTR_SOURCE, DOMAIN, EVENT_AUTOMATION_TRIGGERED
from .trace import DATA_AUTOMATION_TRACE


@callback
def async_describe_events(hass: HomeAssistant, async_describe_event):  # type: ignore
    """Describe logbook events."""

    @callback
    def async_describe_logbook_event(event: LazyEventPartialState):  # type: ignore
        """Describe a logbook event."""
        data = event.data
        message = "has been triggered"
        if ATTR_SOURCE in data:
            message = f"{message} by {data[ATTR_SOURCE]}"

        run_id = None
        if (
            (entity_id := data.get(ATTR_ENTITY_ID))
            and (cur_state := hass.states.get(entity_id))
            and (automation_id := cur_state.attributes.get(CONF_ID))
            and automation_id in hass.data[DATA_AUTOMATION_TRACE]
        ):
            for trace in hass.data[DATA_AUTOMATION_TRACE][automation_id].values():
                if trace.context.id == event.context_id:
                    run_id = trace.run_id
                    break

        return {
            "name": data.get(ATTR_NAME),
            "message": message,
            "source": data.get(ATTR_SOURCE),
            "entity_id": data.get(ATTR_ENTITY_ID),
            "run_id": run_id,
        }

    async_describe_event(
        DOMAIN, EVENT_AUTOMATION_TRIGGERED, async_describe_logbook_event
    )
