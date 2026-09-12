"""LG webOS TV device turn on trigger."""

from functools import partial
from typing import TYPE_CHECKING, Any, cast, override

import voluptuous as vol

from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_OPTIONS,
    CONF_PLATFORM,
    CONF_TARGET,
    CONF_TYPE,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.automation import move_top_level_schema_fields_to_options
from homeassistant.helpers.target import TargetEntityChangeTracker, TargetSelection
from homeassistant.helpers.trigger import (
    PluggableAction,
    Trigger,
    TriggerActionRunner,
    TriggerConfig,
    TriggerNotTriggeredReporter,
)
from homeassistant.helpers.typing import ConfigType

from ..const import DOMAIN
from ..helpers import (
    async_get_device_entry_by_device_id,
    async_get_device_id_from_entity_id,
)

# Stored in device automations as the trigger type; must stay stable
PLATFORM_TYPE = f"{DOMAIN}.turn_on"

_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
        # The trigger has no options, but the editor sends an empty options dict
        vol.Required(CONF_OPTIONS, default={}): {},
    }
)

# Legacy trigger used top-level entity_id/device_id options
_LEGACY_OPTIONS_SCHEMA_DICT: dict[vol.Marker, Any] = {
    vol.Optional(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
}

_LEGACY_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPTIONS): vol.All(
            _LEGACY_OPTIONS_SCHEMA_DICT,
            cv.has_at_least_one_key(ATTR_ENTITY_ID, ATTR_DEVICE_ID),
        )
    }
)


def async_get_turn_on_trigger(device_id: str) -> dict[str, str]:
    """Return data for a turn on trigger."""

    return {
        CONF_PLATFORM: "device",
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
        CONF_TYPE: PLATFORM_TYPE,
    }


@callback
def async_get_turn_on_description(hass: HomeAssistant, device_id: str) -> str:
    """Return the trigger description for a device."""
    device = async_get_device_entry_by_device_id(hass, device_id)
    return f"webostv turn on trigger for {device.name_by_user or device.name}"


@callback
def _async_attach_turn_on_actions(
    hass: HomeAssistant, device_ids: set[str], run_action: TriggerActionRunner
) -> list[CALLBACK_TYPE]:
    """Attach the turn on action for each of the given devices."""

    async def run_turn_on_action(
        description: str,
        variables: dict[str, Any],
        context: Context | None = None,
    ) -> None:
        """Run the action; a coroutine so turn_on can await it."""
        await run_action(variables, description, context)

    return [
        PluggableAction.async_attach_trigger(
            hass,
            async_get_turn_on_trigger(device_id),
            partial(run_turn_on_action, async_get_turn_on_description(hass, device_id)),
            {ATTR_DEVICE_ID: device_id},
        )
        for device_id in device_ids
    ]


class _TurnOnTargetTracker(TargetEntityChangeTracker):
    """Attach turn on actions to the webOS TV devices selected by a target."""

    def __init__(
        self,
        hass: HomeAssistant,
        target_selection: TargetSelection,
        run_action: TriggerActionRunner,
    ) -> None:
        """Initialize the tracker."""

        def entity_filter(entities: set[str]) -> set[str]:
            # Matches the entity filter of the target selector in triggers.yaml
            ent_reg = er.async_get(hass)
            return {
                entity_id
                for entity_id in entities
                if (entry := ent_reg.async_get(entity_id)) is not None
                and entry.platform == DOMAIN
                and entry.domain == Platform.MEDIA_PLAYER
                and entry.device_id is not None
            }

        super().__init__(hass, target_selection, entity_filter)
        self._selection = target_selection
        self._run_action = run_action
        self._device_ids: set[str] = set()
        self._unsubs: list[CALLBACK_TYPE] = []

    @callback
    @override
    def _handle_entities_update(self, tracked_entities: set[str]) -> None:
        """Re-attach the turn on actions when the tracked devices change."""
        ent_reg = er.async_get(self._hass)
        dev_reg = dr.async_get(self._hass)
        # Used as-is: resolving via entities would drop hidden-entity devices.
        device_ids: set[str] = set()
        for device_id in self._selection.device_ids:
            if (
                dev_reg.async_get(device_id, include_composite_devices=False)
                is not None
            ):
                device_ids.add(device_id)
            # A composite id isn't a device; it resolves to its splits.
            elif splits := dev_reg.async_get_devices_for_composite_device_id(device_id):
                device_ids.update(device.id for device in splits)
        device_ids.update(
            entity_device_id
            for entity_id in tracked_entities
            if (entry := ent_reg.async_get(entity_id))
            and (entity_device_id := entry.device_id)
        )
        if device_ids == self._device_ids:
            return

        self._detach_actions()
        self._device_ids = device_ids
        self._unsubs = _async_attach_turn_on_actions(
            self._hass, device_ids, self._run_action
        )

    @callback
    def _detach_actions(self) -> None:
        """Detach the currently attached turn on actions."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    @override
    def _unsubscribe(self) -> None:
        """Unsubscribe from all events."""
        super()._unsubscribe()
        self._detach_actions()
        self._device_ids = set()


class TurnOnTrigger(Trigger):
    """LG webOS TV turn on trigger."""

    _target: dict[str, Any]

    @classmethod
    @override
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, _TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize trigger."""
        super().__init__(hass, config)

        if TYPE_CHECKING:
            assert config.target is not None
        self._target = config.target

    @override
    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,
    ) -> CALLBACK_TYPE:
        """Attach a trigger."""
        target_selection = TargetSelection(self._target)
        if not target_selection.has_any_target:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="trigger_without_target"
            )

        tracker = _TurnOnTargetTracker(self._hass, target_selection, run_action)
        return await tracker.async_setup()


class LegacyTurnOnTrigger(Trigger):
    """Backwards compatible trigger for the legacy webostv.turn_on config."""

    _options: dict[str, Any]

    @classmethod
    @override
    async def async_validate_complete_config(
        cls, hass: HomeAssistant, complete_config: ConfigType
    ) -> ConfigType:
        """Validate complete config, moving legacy fields to options."""
        complete_config = move_top_level_schema_fields_to_options(
            complete_config, _LEGACY_OPTIONS_SCHEMA_DICT
        )
        return await super().async_validate_complete_config(hass, complete_config)

    @classmethod
    @override
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, _LEGACY_TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize trigger."""
        super().__init__(hass, config)

        if TYPE_CHECKING:
            assert config.options is not None
        self._options = config.options

    @override
    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,
    ) -> CALLBACK_TYPE:
        """Attach a trigger."""
        device_ids = set(self._options.get(ATTR_DEVICE_ID, []))
        device_ids.update(
            async_get_device_id_from_entity_id(self._hass, entity_id)
            for entity_id in self._options.get(ATTR_ENTITY_ID, [])
        )

        unsubs = _async_attach_turn_on_actions(self._hass, device_ids, run_action)

        @callback
        def async_remove() -> None:
            """Remove the attached actions."""
            for unsub in unsubs:
                unsub()
            unsubs.clear()

        return async_remove
