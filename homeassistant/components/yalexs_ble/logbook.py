"""Describe Yale Access Bluetooth logbook events."""

from collections.abc import Callable

from yalexs_ble import KEYPAD_MASTER_CODE_SLOT

from homeassistant.components.logbook import (
    LOGBOOK_ENTRY_ENTITY_ID,
    LOGBOOK_ENTRY_MESSAGE,
    LOGBOOK_ENTRY_NAME,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_NAME
from homeassistant.core import Event, HomeAssistant, callback

from .const import (
    ATTR_MASTER_CODE,
    ATTR_SLOT,
    ATTR_SOURCE,
    DOMAIN,
    EVENT_LOCK_ACTIVITY,
    SOURCE_PIN,
    changed_by_for_source,
)

MESSAGE_BY_SOURCE = {
    "manual": "operated manually",
    "auto_lock": "auto locked",
    "remote": "operated remotely",
}


def _message(source: str, slot: int | None, name: str | None, master_code: bool) -> str:
    """Return the logbook message for an activity."""
    if source != SOURCE_PIN:
        return MESSAGE_BY_SOURCE.get(source, source)
    if name:
        return f"keypad code {name} used"
    if master_code:
        return "master code used"
    if slot is not None:
        return f"keypad slot {slot} used"
    return "keypad used"


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, str]]], None],
) -> None:
    """Describe logbook events."""

    @callback
    def async_describe_lock_activity(event: Event) -> dict[str, str]:
        """Describe a lock activity event."""
        data = event.data
        source = data[ATTR_SOURCE]
        master_code = data[ATTR_MASTER_CODE]
        slot = KEYPAD_MASTER_CODE_SLOT if master_code else data[ATTR_SLOT]
        name = data[ATTR_NAME]
        return {
            LOGBOOK_ENTRY_NAME: changed_by_for_source(source, slot, name, name)
            or source,
            LOGBOOK_ENTRY_MESSAGE: _message(source, slot, name, master_code),
            LOGBOOK_ENTRY_ENTITY_ID: data[ATTR_ENTITY_ID],
        }

    async_describe_event(DOMAIN, EVENT_LOCK_ACTIVITY, async_describe_lock_activity)
