"""Describe logbook events."""

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import callback

from .const import DOMAIN, DOOR_STATION, DOOR_STATION_EVENT_ENTITY_IDS


@callback
def async_describe_events(hass, async_describe_event):
    """Describe logbook events."""

    @callback
    def async_describe_logbook_event(event):
        """Describe a logbook event."""
        doorbird_event = event.event_type.split("_", 1)[1]

        return {
            "name": "Doorbird",
            "message": f"Event {event.event_type} was fired.",
            "entity_id": hass.data[DOMAIN][DOOR_STATION_EVENT_ENTITY_IDS].get(
                doorbird_event, event.data.get(ATTR_ENTITY_ID)
            ),
        }

    domain_data = hass.data[DOMAIN]

    for config_entry_id in domain_data:
        door_station = domain_data[config_entry_id][DOOR_STATION]

        for event in door_station.doorstation_events:
            async_describe_event(
                DOMAIN, f"{DOMAIN}_{event}", async_describe_logbook_event
            )
