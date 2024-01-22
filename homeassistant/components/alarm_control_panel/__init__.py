"""Component to interface with an alarm control panel."""
from __future__ import annotations

from datetime import timedelta
from functools import partial
import logging
from typing import TYPE_CHECKING, Any, Final, final

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
from homeassistant.core import HomeAssistant
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

if TYPE_CHECKING:
    from functools import cached_property
else:
    from homeassistant.backports.functools import cached_property

_LOGGER: Final = logging.getLogger(__name__)

SCAN_INTERVAL: Final = timedelta(seconds=30)
ENTITY_ID_FORMAT: Final = DOMAIN + ".{}"

ALARM_SERVICE_SCHEMA: Final = make_entity_service_schema(
    {vol.Optional(ATTR_CODE): cv.string}
)

PLATFORM_SCHEMA: Final = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE: Final = cv.PLATFORM_SCHEMA_BASE

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track states and offer events for sensors."""
    component = hass.data[DOMAIN] = EntityComponent[AlarmControlPanelEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_ALARM_DISARM, ALARM_SERVICE_SCHEMA, "async_alarm_disarm"
    )
    component.async_register_entity_service(
        SERVICE_ALARM_ARM_HOME,
        ALARM_SERVICE_SCHEMA,
        "async_alarm_arm_home",
        [AlarmControlPanelEntityFeature.ARM_HOME],
    )
    component.async_register_entity_service(
        SERVICE_ALARM_ARM_AWAY,
        ALARM_SERVICE_SCHEMA,
        "async_alarm_arm_away",
        [AlarmControlPanelEntityFeature.ARM_AWAY],
    )
    component.async_register_entity_service(
        SERVICE_ALARM_ARM_NIGHT,
        ALARM_SERVICE_SCHEMA,
        "async_alarm_arm_night",
        [AlarmControlPanelEntityFeature.ARM_NIGHT],
    )
    component.async_register_entity_service(
        SERVICE_ALARM_ARM_VACATION,
        ALARM_SERVICE_SCHEMA,
        "async_alarm_arm_vacation",
        [AlarmControlPanelEntityFeature.ARM_VACATION],
    )
    component.async_register_entity_service(
        SERVICE_ALARM_ARM_CUSTOM_BYPASS,
        ALARM_SERVICE_SCHEMA,
        "async_alarm_arm_custom_bypass",
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
    component: EntityComponent[AlarmControlPanelEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[AlarmControlPanelEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


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

    def alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        raise NotImplementedError()

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        await self.hass.async_add_executor_job(self.alarm_disarm, code)

    def alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        raise NotImplementedError()

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        await self.hass.async_add_executor_job(self.alarm_arm_home, code)

    def alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        raise NotImplementedError()

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self.hass.async_add_executor_job(self.alarm_arm_away, code)

    def alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        raise NotImplementedError()

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        await self.hass.async_add_executor_job(self.alarm_arm_night, code)

    def alarm_arm_vacation(self, code: str | None = None) -> None:
        """Send arm vacation command."""
        raise NotImplementedError()

    async def async_alarm_arm_vacation(self, code: str | None = None) -> None:
        """Send arm vacation command."""
        await self.hass.async_add_executor_job(self.alarm_arm_vacation, code)

    def alarm_trigger(self, code: str | None = None) -> None:
        """Send alarm trigger command."""
        raise NotImplementedError()

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Send alarm trigger command."""
        await self.hass.async_add_executor_job(self.alarm_trigger, code)

    def alarm_arm_custom_bypass(self, code: str | None = None) -> None:
        """Send arm custom bypass command."""
        raise NotImplementedError()

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


# As we import constants of the const module here, we need to add the following
# functions to check for deprecated constants again
# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
