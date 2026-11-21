"""Offer template automation rules."""

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import Any, Final, override

import probatio

from homeassistant import exceptions
from homeassistant.const import (
    CONF_FOR,
    CONF_PLATFORM,
    CONF_TARGET,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HassJob,
    HomeAssistant,
    callback,
)
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.event import (
    TrackTemplate,
    TrackTemplateResult,
    TrackTemplateResultInfo,
    async_call_later,
    async_track_template_result,
)
from homeassistant.helpers.target import TargetEntityChangeTracker, TargetSelection
from homeassistant.helpers.template import Template, result_as_boolean
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

ATTR_ENTITY_IDS: Final = "entity_ids"

TRIGGER_SCHEMA = IF_ACTION_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        probatio.Required(CONF_PLATFORM): "template",
        probatio.Required(CONF_VALUE_TEMPLATE): cv.template,
        probatio.Optional(CONF_FOR): cv.positive_time_period_template,
        probatio.Optional(CONF_TARGET): probatio.All(
            cv.TARGET_FIELDS, cv.exclude_requires_target
        ),
    }
)


def _all_entities(entity_ids: set[str]) -> set[str]:
    """Return all targeted entities, the template trigger accepts any domain."""
    return entity_ids


class _TargetEntitiesTracker(TargetEntityChangeTracker):
    """Report the entities a target resolves to whenever they may have changed."""

    def __init__(
        self,
        hass: HomeAssistant,
        target_selection: TargetSelection,
        on_update: Callable[[set[str]], None],
    ) -> None:
        """Initialize the tracker."""
        super().__init__(hass, target_selection, _all_entities)
        self._on_update = on_update

    @callback
    @override
    def _handle_entities_update(self, tracked_entities: set[str]) -> None:
        """Pass the resolved entities on."""
        self._on_update(tracked_entities)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
    *,
    platform_type: str = "template",
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    trigger_data = trigger_info["trigger_data"]
    variables = dict(trigger_info["variables"] or {})
    value_template: Template = config[CONF_VALUE_TEMPLATE]
    time_delta = config.get(CONF_FOR)
    delay_cancel = None
    job = HassJob(action)
    armed = False
    template_info: TrackTemplateResultInfo | None = None
    target_unsub: CALLBACK_TYPE | None = None

    @callback
    def update_entity_ids(entity_ids: set[str]) -> None:
        """Re-render the template when the targeted entities change."""
        if (new_entity_ids := sorted(entity_ids)) == variables.get(ATTR_ENTITY_IDS):
            return
        # The template tracker renders with this dict, so updating it in place
        # makes the refresh use the new entity ids.
        variables[ATTR_ENTITY_IDS] = new_entity_ids
        if template_info is not None:
            template_info.async_refresh()

    if CONF_TARGET in config:
        target_unsub = await _TargetEntitiesTracker(
            hass, TargetSelection(config[CONF_TARGET]), update_entity_ids
        ).async_setup()

    # Arm at setup if the template is already false.
    try:
        if not result_as_boolean(value_template.async_render(variables)):
            armed = True
    except exceptions.TemplateError as ex:
        _LOGGER.warning(
            "Error initializing 'template' trigger for '%s': %s",
            trigger_info["name"],
            ex,
        )

    @callback
    def template_listener(
        event: Event[EventStateChangedData] | None,
        updates: list[TrackTemplateResult],
    ) -> None:
        """Listen for state changes and calls action."""
        nonlocal delay_cancel, armed
        result = updates.pop().result

        if isinstance(result, exceptions.TemplateError):
            _LOGGER.warning(
                "Error evaluating 'template' trigger for '%s': %s",
                trigger_info["name"],
                result,
            )
            return

        if delay_cancel:
            delay_cancel()
            delay_cancel = None

        if not result_as_boolean(result):
            armed = True
            return

        # Only fire when previously armed.
        if not armed:
            return

        # Fire!
        armed = False

        entity_id = event and event.data["entity_id"]
        from_s = event and event.data["old_state"]
        to_s = event and event.data["new_state"]

        if entity_id is not None:
            description = f"{entity_id} via template"
        else:
            description = "time change or manual update via template"

        template_variables = {
            "platform": platform_type,
            "entity_id": entity_id,
            "from_state": from_s,
            "to_state": to_s,
        }
        trigger_variables = {
            **trigger_data,
            "for": time_delta,
            "description": description,
        }

        @callback
        def call_action(*_: Any) -> None:
            """Call action with right context."""
            nonlocal trigger_variables
            hass.async_run_hass_job(
                job,
                {"trigger": {**template_variables, **trigger_variables}},
                (to_s.context if to_s else None),
            )

        if not time_delta:
            call_action()
            return

        data = {"trigger": template_variables}
        period_variables = {**variables, **data}

        try:
            period: timedelta = cv.positive_time_period(
                template.render_complex(time_delta, period_variables)
            )
        except (exceptions.TemplateError, probatio.Invalid) as ex:
            _LOGGER.error(
                "Error rendering '%s' for template: %s", trigger_info["name"], ex
            )
            return

        trigger_variables["for"] = period

        delay_cancel = async_call_later(hass, period.total_seconds(), call_action)

    template_info = async_track_template_result(
        hass,
        [TrackTemplate(value_template, variables)],
        template_listener,
    )

    @callback
    def async_remove():
        """Remove state listeners async."""
        if target_unsub:
            target_unsub()
        template_info.async_remove()
        if delay_cancel:
            delay_cancel()

    return async_remove
