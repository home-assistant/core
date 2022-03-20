"""Support for Yale Alarm."""
from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol
from yalesmartalarmclient.const import (
    YALE_STATE_ARM_FULL,
    YALE_STATE_ARM_PARTIAL,
    YALE_STATE_DISARM,
)

from homeassistant.components.alarm_control_panel import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    AlarmControlPanelEntity,
)
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType

from .const import (
    CONF_AREA_ID,
    COORDINATOR,
    DEFAULT_AREA_ID,
    DEFAULT_NAME,
    DOMAIN,
    LOGGER,
    STATE_MAP,
    YALE_ALL_ERRORS,
)
from .coordinator import YaleDataUpdateCoordinator
from .entity import YaleAlarmEntity

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_AREA_ID, default=DEFAULT_AREA_ID): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import Yale configuration from YAML."""
    LOGGER.warning(
        "Loading Yale Alarm via platform setup is deprecated; Please remove it from your configuration"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the alarm entry."""

    async_add_entities(
        [YaleAlarmDevice(coordinator=hass.data[DOMAIN][entry.entry_id][COORDINATOR])]
    )


class YaleAlarmDevice(YaleAlarmEntity, AlarmControlPanelEntity):
    """Represent a Yale Smart Alarm."""

    coordinator: YaleDataUpdateCoordinator

    _attr_code_arm_required = False
    _attr_supported_features = SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY

    def __init__(self, coordinator: YaleDataUpdateCoordinator) -> None:
        """Initialize the Yale Alarm Device."""
        super().__init__(coordinator)
        self._attr_name = coordinator.entry.data[CONF_NAME]
        self._attr_unique_id = coordinator.entry.entry_id

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        return await self.async_set_alarm(YALE_STATE_DISARM, code)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        return await self.async_set_alarm(YALE_STATE_ARM_PARTIAL, code)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        return await self.async_set_alarm(YALE_STATE_ARM_FULL, code)

    async def async_set_alarm(self, command: str, code: str | None = None) -> None:
        """Set alarm."""
        if TYPE_CHECKING:
            assert self.coordinator.yale, "Connection to API is missing"

        try:
            if command == YALE_STATE_ARM_FULL:
                alarm_state = await self.hass.async_add_executor_job(
                    self.coordinator.yale.arm_full
                )
            if command == YALE_STATE_ARM_PARTIAL:
                alarm_state = await self.hass.async_add_executor_job(
                    self.coordinator.yale.arm_partial
                )
            if command == YALE_STATE_DISARM:
                alarm_state = await self.hass.async_add_executor_job(
                    self.coordinator.yale.disarm
                )
        except YALE_ALL_ERRORS as error:
            raise HomeAssistantError(
                f"Could not set alarm for {self._attr_name}: {error}"
            ) from error

        if alarm_state:
            self.coordinator.data["alarm"] = command
            self.async_write_ha_state()
            return
        raise HomeAssistantError(
            "Could not change alarm check system ready for arming."
        )

    @property
    def available(self) -> bool:
        """Return True if alarm is available."""
        if STATE_MAP.get(self.coordinator.data["alarm"]) is None:
            return False
        return super().available

    @property
    def state(self) -> StateType:
        """Return the state of the alarm."""
        return STATE_MAP.get(self.coordinator.data["alarm"])
