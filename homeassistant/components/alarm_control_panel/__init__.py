"""Component to interface with an alarm control panel."""

from __future__ import annotations

from datetime import timedelta
from functools import cached_property, partial
import logging
from typing import Any, Final, final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CODE,
    ATTR_CODE_FORMAT,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_CUSTOM_BYPASS,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_ARM_VACATION,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import make_entity_service_schema
from homeassistant.helpers.deprecation import (
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import (  # noqa: F401
    _DEPRECATED_FORMAT_NUMBER,
    _DEPRECATED_FORMAT_TEXT,
    _DEPRECATED_SUPPORT_ALARM_ARM_AWAY,
    _DEPRECATED_SUPPORT_ALARM_ARM_CUSTOM_BYPASS,
    _DEPRECATED_SUPPORT_ALARM_ARM_HOME,
    _DEPRECATED_SUPPORT_ALARM_ARM_NIGHT,
    _DEPRECATED_SUPPORT_ALARM_ARM_VACATION,
    _DEPRECATED_SUPPORT_ALARM_TRIGGER,
    ATTR_CHANGED_BY,
    ATTR_CODE_ARM_REQUIRED,
    DOMAIN,
    AlarmControlPanelEntityFeature,
    CodeFormat,
)

_LOGGER: Final = logging.getLogger(__name__)

DATA_COMPONENT: HassKey[EntityComponent[AlarmControlPanelEntity]] = HassKey(DOMAIN)
ENTITY_ID_FORMAT: Final = DOMAIN + ".{}"
PLATFORM_SCHEMA: Final = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE: Final = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL: Final = timedelta(seconds=30)

CONF_DEFAULT_CODE = "default_code"

ALARM_SERVICE_SCHEMA: Final = make_entity_service_schema(
    {vol.Optional(ATTR_CODE): cv.string}
)


# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track states and offer events for sensors."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[AlarmControlPanelEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_ALARM_DISARM,
        ALARM_SERVICE_SCHEMA,
        "async_handle_alarm_disarm",
    )
    component.async_register_entity_service(
        SERVICE_ALARM_ARM_HOME,
        ALARM_SERVICE_SCHEMA,
        "async_handle_alarm_arm_home",
        [AlarmControlPanelEntityFeature.ARM_HOME],
    )
    component.async_register_entity_service(
        SERVICE_ALARM_ARM_AWAY,
        ALARM_SERVICE_SCHEMA,
        "async_handle_alarm_arm_away",
        [AlarmControlPanelEntityFeature.ARM_AWAY],
    )
    component.async_register_entity_service(
        SERVICE_ALARM_ARM_NIGHT,
        ALARM_SERVICE_SCHEMA,
        "async_handle_alarm_arm_night",
        [AlarmControlPanelEntityFeature.ARM_NIGHT],
    )
    component.async_register_entity_service(
        SERVICE_ALARM_ARM_VACATION,
        ALARM_SERVICE_SCHEMA,
        "async_handle_alarm_arm_vacation",
        [AlarmControlPanelEntityFeature.ARM_VACATION],
    )
    component.async_register_entity_service(
        SERVICE_ALARM_ARM_CUSTOM_BYPASS,
        ALARM_SERVICE_SCHEMA,
        "async_handle_alarm_arm_custom_bypass",
        [AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS],
    )
    component.async_register_entity_service(
        SERVICE_ALARM_TRIGGER,
        ALARM_SERVICE_SCHEMA,
        "async_alarm_trigger",
        [AlarmControlPanelEntityFeature.TRIGGER],
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


class AlarmControlPanelEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes alarm control panel entities."""


CACHED_PROPERTIES_WITH_ATTR_ = {
    "code_format",
    "changed_by",
    "code_arm_required",
    "supported_features",
}


class AlarmControlPanelEntity(Entity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """An abstract class for alarm control entities."""

    entity_description: AlarmControlPanelEntityDescription
    _attr_changed_by: str | None = None
    _attr_code_arm_required: bool = True
    _attr_code_format: CodeFormat | None = None
    _attr_supported_features: AlarmControlPanelEntityFeature = (
        AlarmControlPanelEntityFeature(0)
    )
    _alarm_control_panel_option_default_code: str | None = None

    @final
    @callback
    def code_or_default_code(self, code: str | None) -> str | None:
        """Return code to use for a service call.

        If the passed in code is not None, it will be returned. Otherwise return the
        default code, if set, or None if not set, is returned.
        """
        if code:
            # Return code provided by user
            return code
        # Fallback to default code or None if not set
        return self._alarm_control_panel_option_default_code

    @cached_property
    def code_format(self) -> CodeFormat | None:
        """Code format or None if no code is required."""
        return self._attr_code_format

    @cached_property
    def changed_by(self) -> str | None:
        """Last change triggered by."""
        return self._attr_changed_by

    @cached_property
    def code_arm_required(self) -> bool:
        """Whether the code is required for arm actions."""
        return self._attr_code_arm_required

    @final
    @callback
    def check_code_arm_required(self, code: str | None) -> str | None:
        """Check if arm code is required, raise if no code is given."""
        if not (_code := self.code_or_default_code(code)) and self.code_arm_required:
            raise ServiceValidationError(
                f"Arming requires a code but none was given for {self.entity_id}",
                translation_domain=DOMAIN,
                translation_key="code_arm_required",
                translation_placeholders={
                    "entity_id": self.entity_id,
                },
            )
        return _code

    @final
    async def async_handle_alarm_disarm(self, code: str | None = None) -> None:
        """Add default code and disarm."""
        await self.async_alarm_disarm(self.code_or_default_code(code))

    def alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        raise NotImplementedError

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        await self.hass.async_add_executor_job(self.alarm_disarm, code)

    @final
    async def async_handle_alarm_arm_home(self, code: str | None = None) -> None:
        """Add default code and arm home."""
        await self.async_alarm_arm_home(self.check_code_arm_required(code))

    def alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        raise NotImplementedError

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        await self.hass.async_add_executor_job(self.alarm_arm_home, code)

    @final
    async def async_handle_alarm_arm_away(self, code: str | None = None) -> None:
        """Add default code and arm away."""
        await self.async_alarm_arm_away(self.check_code_arm_required(code))

    def alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        raise NotImplementedError

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self.hass.async_add_executor_job(self.alarm_arm_away, code)

    @final
    async def async_handle_alarm_arm_night(self, code: str | None = None) -> None:
        """Add default code and arm night."""
        await self.async_alarm_arm_night(self.check_code_arm_required(code))

    def alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        raise NotImplementedError

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        await self.hass.async_add_executor_job(self.alarm_arm_night, code)

    @final
    async def async_handle_alarm_arm_vacation(self, code: str | None = None) -> None:
        """Add default code and arm vacation."""
        await self.async_alarm_arm_vacation(self.check_code_arm_required(code))

    def alarm_arm_vacation(self, code: str | None = None) -> None:
        """Send arm vacation command."""
        raise NotImplementedError

    async def async_alarm_arm_vacation(self, code: str | None = None) -> None:
        """Send arm vacation command."""
        await self.hass.async_add_executor_job(self.alarm_arm_vacation, code)

    def alarm_trigger(self, code: str | None = None) -> None:
        """Send alarm trigger command."""
        raise NotImplementedError

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Send alarm trigger command."""
        await self.hass.async_add_executor_job(self.alarm_trigger, code)

    @final
    async def async_handle_alarm_arm_custom_bypass(
        self, code: str | None = None
    ) -> None:
        """Add default code and arm custom bypass."""
        await self.async_alarm_arm_custom_bypass(self.check_code_arm_required(code))

    def alarm_arm_custom_bypass(self, code: str | None = None) -> None:
        """Send arm custom bypass command."""
        raise NotImplementedError

    async def async_alarm_arm_custom_bypass(self, code: str | None = None) -> None:
        """Send arm custom bypass command."""
        await self.hass.async_add_executor_job(self.alarm_arm_custom_bypass, code)

    @cached_property
    def supported_features(self) -> AlarmControlPanelEntityFeature:
        """Return the list of supported features."""
        features = self._attr_supported_features
        if type(features) is int:  # noqa: E721
            new_features = AlarmControlPanelEntityFeature(features)
            self._report_deprecated_supported_features_values(new_features)
            return new_features
        return features

    @final
    @property
    def state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        return {
            ATTR_CODE_FORMAT: self.code_format,
            ATTR_CHANGED_BY: self.changed_by,
            ATTR_CODE_ARM_REQUIRED: self.code_arm_required,
        }

    async def async_internal_added_to_hass(self) -> None:
        """Call when the alarm control panel entity is added to hass."""
        await super().async_internal_added_to_hass()
        if not self.registry_entry:
            return
        self._async_read_entity_options()

    @callback
    def async_registry_entry_updated(self) -> None:
        """Run when the entity registry entry has been updated."""
        self._async_read_entity_options()

    @callback
    def _async_read_entity_options(self) -> None:
        """Read entity options from entity registry.

        Called when the entity registry entry has been updated and before the
        alarm control panel is added to the state machine.
        """
        assert self.registry_entry
        if (alarm_options := self.registry_entry.options.get(DOMAIN)) and (
            default_code := alarm_options.get(CONF_DEFAULT_CODE)
        ):
            self._alarm_control_panel_option_default_code = default_code
            return
        self._alarm_control_panel_option_default_code = None


# As we import constants of the const module here, we need to add the following
# functions to check for deprecated constants again
# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
