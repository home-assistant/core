"""Support for Yale Alarm."""
from __future__ import annotations

import voluptuous as vol
from yalesmartalarmclient.client import (
    YALE_STATE_ARM_FULL,
    YALE_STATE_ARM_PARTIAL,
    YALE_STATE_DISARM,
)

from homeassistant.components.alarm_control_panel import (
    ATTR_CHANGED_BY,
    ATTR_CODE_ARM_REQUIRED,
    ATTR_CODE_FORMAT,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    AlarmControlPanelEntity,
)
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_UNAVAILABLE,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_ONLINE,
    ATTR_STATUS,
    CONF_AREA_ID,
    DEFAULT_AREA_ID,
    DEFAULT_NAME,
    DOMAIN,
    LOGGER,
    MANUFACTURER,
    MODEL,
)

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_AREA_ID, default=DEFAULT_AREA_ID): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Import Yale configuration from YAML."""
    LOGGER.warning(
        "Loading Yale Alarm via platform setup is depreciated; Please remove it from your configuration"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the alarm entry."""

    async_add_entities(
        [YaleAlarmDevice(coordinator=hass.data[DOMAIN][entry.entry_id]["coordinator"])]
    )


class YaleAlarmDevice(CoordinatorEntity, AlarmControlPanelEntity):
    """Represent a Yale Smart Alarm."""

    _state_map = {
        YALE_STATE_DISARM: STATE_ALARM_DISARMED,
        YALE_STATE_ARM_PARTIAL: STATE_ALARM_ARMED_HOME,
        YALE_STATE_ARM_FULL: STATE_ALARM_ARMED_AWAY,
    }

    _state = STATE_UNAVAILABLE

    @property
    def name(self):
        """Return the name of the device."""
        return self.coordinator.entry.data[CONF_NAME]

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return str(self.coordinator.entry.entry_id)  # type: ignore[attr-defined]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return {
            ATTR_NAME: self.coordinator.entry.data[CONF_NAME],  # type: ignore[attr-defined]
            ATTR_MANUFACTURER: MANUFACTURER,
            ATTR_MODEL: MODEL,
            ATTR_IDENTIFIERS: {(DOMAIN, self.coordinator.entry.data[CONF_USERNAME])},  # type: ignore[attr-defined]
        }

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def code_arm_required(self):
        """Whether the code is required for arm actions."""
        return False

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        self.coordinator.yale.disarm()

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        self.coordinator.yale.arm_partial()

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        self.coordinator.yale.arm_full()

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_CODE_FORMAT: self.code_format,
            ATTR_CHANGED_BY: self.changed_by,
            ATTR_CODE_ARM_REQUIRED: self.code_arm_required,
            ATTR_ONLINE: self.coordinator.data["online"],
            ATTR_STATUS: self.coordinator.data["status"],
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self._state_map.get(
            self.coordinator.data["alarm"], STATE_UNAVAILABLE
        )
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
