"""Helper methods for message subscription."""
import logging
from typing import Any, Callable, Iterable, Union

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import _async_remove_indexed_listeners
from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)


TRACK_STATELESS_PROGRAMMABLE_SWITCH_PRESSED_CALLBACKS = (
    "homekit.track_programmable_switch_pressed_callbacks"
)
TRACK_STATELESS_PROGRAMMABLE_SWITCH_PRESSED_LISTENER = (
    "homekit.track_programmable_switch_pressed_listener"
)
EVENT_STATELESS_PROGRAMMABLE_SWITCH_PRESSED = (
    "sensor.stateless_programmable_switch.pressed"
)


@bind_hass
def async_track_stateless_programmable_switch_pressed(
    hass: HomeAssistant,
    entity_ids: Union[str, Iterable[str]],
    action: Callable[[Event], Any],
) -> Callable[[], None]:
    """Tracks stateless programmable switch pressed events."""

    entity_callbacks = hass.data.setdefault(
        TRACK_STATELESS_PROGRAMMABLE_SWITCH_PRESSED_CALLBACKS, {}
    )
    if TRACK_STATELESS_PROGRAMMABLE_SWITCH_PRESSED_LISTENER not in hass.data:

        @callback
        def _async_stateless_programmable_switch_pressed_dispatcher(
            event: Event,
        ) -> None:
            """Dispatch state changes by entity_id."""
            entity_id = event.data.get("entity_id")

            if entity_id not in entity_callbacks:
                return

            for action in entity_callbacks[entity_id][:]:
                try:
                    hass.async_run_job(action, event)
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception(
                        "Error while processing %s event for %s",
                        EVENT_STATELESS_PROGRAMMABLE_SWITCH_PRESSED,
                        entity_id,
                    )

        hass.data[
            TRACK_STATELESS_PROGRAMMABLE_SWITCH_PRESSED_LISTENER
        ] = hass.bus.async_listen(
            EVENT_STATELESS_PROGRAMMABLE_SWITCH_PRESSED,
            _async_stateless_programmable_switch_pressed_dispatcher,
        )

    if isinstance(entity_ids, str):
        entity_ids = [entity_ids]

    entity_ids = [entity_id.lower() for entity_id in entity_ids]

    for entity_id in entity_ids:
        entity_callbacks.setdefault(entity_id, []).append(action)

    @callback
    def remove_listener() -> None:
        """Remove state change listener."""
        _async_remove_indexed_listeners(
            hass,
            TRACK_STATELESS_PROGRAMMABLE_SWITCH_PRESSED_CALLBACKS,
            TRACK_STATELESS_PROGRAMMABLE_SWITCH_PRESSED_LISTENER,
            entity_ids,
            action,
        )

    return remove_listener
