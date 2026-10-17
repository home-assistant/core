"""Track templates that a trigger renders when it is set up."""

from collections.abc import Callable
import logging
from typing import Any

from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.area_registry import EVENT_AREA_REGISTRY_UPDATED
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import EVENT_DEVICE_REGISTRY_UPDATED
from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED
from homeassistant.helpers.event import (
    TrackTemplate,
    TrackTemplateResult,
    async_track_template_result,
)
from homeassistant.helpers.floor_registry import EVENT_FLOOR_REGISTRY_UPDATED
from homeassistant.helpers.label_registry import EVENT_LABEL_REGISTRY_UPDATED
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import TemplateVarsType

_LOGGER = logging.getLogger(__name__)

_REGISTRY_DEBOUNCE_COOLDOWN = 1


@callback
def async_track_trigger_template(
    hass: HomeAssistant,
    template: Template,
    variables: TemplateVarsType,
    on_change: Callable[[Any], None],
    on_error: Callable[[TemplateError], None],
    *,
    parse_result: bool = False,
) -> tuple[Any, CALLBACK_TYPE]:
    """Render a setup-time template now and call on_change when its result changes.

    The initial render raises on errors, so a broken template still fails
    the trigger setup. Later render errors are passed to on_error and the
    last good result stays in place.

    Returns the initial result and a callback to stop tracking.
    """
    result = template.async_render(variables, parse_result=parse_result)
    if template.is_static:
        return result, lambda: None

    last_result = result

    @callback
    def _async_template_updated(
        event: Event[EventStateChangedData] | None, updates: list[TrackTemplateResult]
    ) -> None:
        """Handle a new result of the template."""
        nonlocal last_result

        result = updates[0].result
        if isinstance(result, TemplateError):
            on_error(result)
            return

        if result == last_result:
            return

        last_result = result
        on_change(result)

    tracker = async_track_template_result(
        hass,
        [TrackTemplate(template, variables, parse_result=parse_result)],
        _async_template_updated,
    )

    # Rendering does not record registry reads (like device_attr or
    # area_name), so any registry update re-renders. Registries change
    # rarely and in bursts, hence the debounce. Refreshing through the
    # tracker keeps its state listeners in line with the new render.
    debouncer = Debouncer(
        hass,
        _LOGGER,
        cooldown=_REGISTRY_DEBOUNCE_COOLDOWN,
        immediate=False,
        function=tracker.async_refresh,
    )

    @callback
    def _async_registry_updated(event: Event[Any]) -> None:
        """Schedule a re-render after a registry update."""
        debouncer.async_schedule_call()

    remove_registry_listeners = [
        hass.bus.async_listen(EVENT_AREA_REGISTRY_UPDATED, _async_registry_updated),
        hass.bus.async_listen(EVENT_DEVICE_REGISTRY_UPDATED, _async_registry_updated),
        hass.bus.async_listen(EVENT_ENTITY_REGISTRY_UPDATED, _async_registry_updated),
        hass.bus.async_listen(EVENT_FLOOR_REGISTRY_UPDATED, _async_registry_updated),
        hass.bus.async_listen(EVENT_LABEL_REGISTRY_UPDATED, _async_registry_updated),
    ]

    @callback
    def _async_remove() -> None:
        """Stop tracking the template."""
        for remove_listener in remove_registry_listeners:
            remove_listener()
        debouncer.async_shutdown()
        tracker.async_remove()

    return result, _async_remove
