"""Component to interface with an alarm control panel."""
from abc import abstractmethod
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.const import (
    ATTR_CODE,
    ATTR_CODE_FORMAT,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_CUSTOM_BYPASS,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
    make_entity_service_schema,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent

from .const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_CUSTOM_BYPASS,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
    SUPPORT_ALARM_TRIGGER,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "alarm_control_panel"
SCAN_INTERVAL = timedelta(seconds=30)
ATTR_CHANGED_BY = "changed_by"
FORMAT_TEXT = "text"
FORMAT_NUMBER = "number"
ATTR_CODE_ARM_REQUIRED = "code_arm_required"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

ALARM_SERVICE_SCHEMA = make_entity_service_schema({vol.Optional(ATTR_CODE): cv.string})


async def async_setup(hass, config):
    """Track states and offer events for sensors."""
    component = hass.data[DOMAIN] = EntityComponent(
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_ALARM_DISARM, ALARM_SERVICE_SCHEMA, "async_alarm_disarm"
    )
    component.async_register_entity_service(
        SERVICE_ALARM_ARM_HOME,
        ALARM_SERVICE_SCHEMA,
        "async_alarm_arm_home",
        [SUPPORT_ALARM_ARM_HOME],
    )
    component.async_register_entity_service(
        SERVICE_ALARM_ARM_AWAY,
        ALARM_SERVICE_SCHEMA,
        "async_alarm_arm_away",
        [SUPPORT_ALARM_ARM_AWAY],
    )
    component.async_register_entity_service(
        SERVICE_ALARM_ARM_NIGHT,
        ALARM_SERVICE_SCHEMA,
        "async_alarm_arm_night",
        [SUPPORT_ALARM_ARM_NIGHT],
    )
    component.async_register_entity_service(
        SERVICE_ALARM_ARM_CUSTOM_BYPASS,
        ALARM_SERVICE_SCHEMA,
        "async_alarm_arm_custom_bypass",
        [SUPPORT_ALARM_ARM_CUSTOM_BYPASS],
    )
    component.async_register_entity_service(
        SERVICE_ALARM_TRIGGER,
        ALARM_SERVICE_SCHEMA,
        "async_alarm_trigger",
        [SUPPORT_ALARM_TRIGGER],
    )

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class AlarmControlPanelEntity(Entity):
    """An abstract class for alarm control entities."""

    @property
    def code_format(self):
        """Regex for code format or None if no code is required."""
        return None

    @property
    def changed_by(self):
        """Last change triggered by."""
        return None

    @property
    def code_arm_required(self):
        """Whether the code is required for arm actions."""
        return True

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        raise NotImplementedError()

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        await self.hass.async_add_executor_job(self.alarm_disarm, code)

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        raise NotImplementedError()

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        await self.hass.async_add_executor_job(self.alarm_arm_home, code)

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        raise NotImplementedError()

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        await self.hass.async_add_executor_job(self.alarm_arm_away, code)

    def alarm_arm_night(self, code=None):
        """Send arm night command."""
        raise NotImplementedError()

    async def async_alarm_arm_night(self, code=None):
        """Send arm night command."""
        await self.hass.async_add_executor_job(self.alarm_arm_night, code)

    def alarm_trigger(self, code=None):
        """Send alarm trigger command."""
        raise NotImplementedError()

    async def async_alarm_trigger(self, code=None):
        """Send alarm trigger command."""
        await self.hass.async_add_executor_job(self.alarm_trigger, code)

    def alarm_arm_custom_bypass(self, code=None):
        """Send arm custom bypass command."""
        raise NotImplementedError()

    async def async_alarm_arm_custom_bypass(self, code=None):
        """Send arm custom bypass command."""
        await self.hass.async_add_executor_job(self.alarm_arm_custom_bypass, code)

    @property
    @abstractmethod
    def supported_features(self) -> int:
        """Return the list of supported features."""

    @property
    def state_attributes(self):
        """Return the state attributes."""
        state_attr = {
            ATTR_CODE_FORMAT: self.code_format,
            ATTR_CHANGED_BY: self.changed_by,
            ATTR_CODE_ARM_REQUIRED: self.code_arm_required,
        }
        return state_attr


class AlarmControlPanel(AlarmControlPanelEntity):
    """An abstract class for alarm control entities (for backwards compatibility)."""

    def __init_subclass__(cls, **kwargs):
        """Print deprecation warning."""
        super().__init_subclass__(**kwargs)
        _LOGGER.warning(
            "AlarmControlPanel is deprecated, modify %s to extend AlarmControlPanelEntity",
            cls.__name__,
        )
