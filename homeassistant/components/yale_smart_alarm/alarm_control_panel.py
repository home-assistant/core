"""Support for Yale Alarm."""
from __future__ import annotations

import voluptuous as vol
from yalesmartalarmclient.const import (
    YALE_STATE_ARM_FULL,
    YALE_STATE_ARM_PARTIAL,
    YALE_STATE_DISARM,
)
from yalesmartalarmclient.exceptions import AuthenticationError, UnknownError

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_AREA_ID,
    COORDINATOR,
    DEFAULT_AREA_ID,
    DEFAULT_NAME,
    DOMAIN,
    LOGGER,
    MANUFACTURER,
    MODEL,
    STATE_MAP,
)
from .coordinator import YaleDataUpdateCoordinator

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


class YaleAlarmDevice(CoordinatorEntity, AlarmControlPanelEntity):
    """Represent a Yale Smart Alarm."""

    _attr_code_arm_required = False
    _attr_supported_features = SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY

    def __init__(self, coordinator: YaleDataUpdateCoordinator) -> None:
        """Initialize the Yale Alarm Device."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._attr_name = coordinator.entry.data[CONF_NAME]
        self._attr_unique_id = coordinator.entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.data[CONF_USERNAME])},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=self._attr_name,
        )

    async def async_alarm_disarm(self, code=None) -> None:
        """Send disarm command."""
        if self._coordinator.yale:
            try:
                alarm_state = await self.hass.async_add_executor_job(
                    self._coordinator.yale.disarm
                )
            except (
                AuthenticationError,
                ConnectionError,
                TimeoutError,
                UnknownError,
            ) as error:
                raise HomeAssistantError(
                    f"Could not verify disarmed for {self._attr_name}: {error}"
                ) from error

        if alarm_state:
            self._attr_state = STATE_MAP.get(YALE_STATE_DISARM)
            self.async_write_ha_state()
        LOGGER.debug("Alarm disarmed: %s", alarm_state)

    async def async_alarm_arm_home(self, code=None) -> None:
        """Send arm home command."""
        if self._coordinator.yale:
            try:
                alarm_state = await self.hass.async_add_executor_job(
                    self._coordinator.yale.arm_partial
                )
            except (
                AuthenticationError,
                ConnectionError,
                TimeoutError,
                UnknownError,
            ) as error:
                raise HomeAssistantError(
                    f"Could not verify armed home for {self._attr_name}: {error}"
                ) from error

        if alarm_state:
            self._attr_state = STATE_MAP.get(YALE_STATE_ARM_PARTIAL)
            self.async_write_ha_state()
        LOGGER.debug("Alarm armed home: %s", alarm_state)

    async def async_alarm_arm_away(self, code=None) -> None:
        """Send arm away command."""
        if self._coordinator.yale:
            try:
                alarm_state = await self.hass.async_add_executor_job(
                    self._coordinator.yale.arm_full
                )
            except (
                AuthenticationError,
                ConnectionError,
                TimeoutError,
                UnknownError,
            ) as error:
                raise HomeAssistantError(
                    f"Could not verify armed away for {self._attr_name}: {error}"
                ) from error

        if alarm_state:
            self._attr_state = STATE_MAP.get(YALE_STATE_ARM_FULL)
            self.async_write_ha_state()
        LOGGER.debug("Alarm armed away: %s", alarm_state)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_state = STATE_MAP.get(self.coordinator.data["alarm"])
        self._attr_available = STATE_MAP.get(self.coordinator.data["alarm"]) is not None
        super()._handle_coordinator_update()
