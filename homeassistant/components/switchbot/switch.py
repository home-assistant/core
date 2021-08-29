"""Support for Switchbot bot."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.switch import (
    DEVICE_CLASS_SWITCH,
    PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_MAC, CONF_NAME, CONF_PASSWORD, CONF_SENSOR_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_BOT,
    CONF_RETRY_COUNT,
    DATA_COORDINATOR,
    DEFAULT_NAME,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import SwitchbotDataUpdateCoordinator

# Initialize the logger
_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 1

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MAC): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: entity_platform.AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import yaml config and initiates config flow for Switchbot devices."""

    # Check if entry config exists and skips import if it does.
    if hass.config_entries.async_entries(DOMAIN):
        return

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_NAME: config[CONF_NAME],
                CONF_PASSWORD: config.get(CONF_PASSWORD, None),
                CONF_MAC: config[CONF_MAC].replace("-", ":").lower(),
                CONF_SENSOR_TYPE: ATTR_BOT,
            },
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
) -> None:
    """Set up Switchbot based on a config entry."""
    coordinator: SwitchbotDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    bot_device = []

    if entry.data[CONF_SENSOR_TYPE] == ATTR_BOT:
        bot_device.append(
            SwitchBot(
                coordinator,
                entry.unique_id,
                entry.data[CONF_MAC],
                entry.data[CONF_NAME],
                entry.data.get(CONF_PASSWORD, None),
                entry.options[CONF_RETRY_COUNT],
            )
        )

    async_add_entities(bot_device)


class SwitchBot(CoordinatorEntity, SwitchEntity, RestoreEntity):
    """Representation of a Switchbot."""

    coordinator: SwitchbotDataUpdateCoordinator

    def __init__(
        self,
        coordinator: SwitchbotDataUpdateCoordinator,
        idx: str | None,
        mac: str,
        name: str,
        password: str,
        retry_count: int,
    ) -> None:
        """Initialize the Switchbot."""
        super().__init__(coordinator)
        self._idx = idx
        self._state: bool | None = None
        self._last_run_success: bool | None = None
        self._model = self.coordinator.data[self._idx]["modelName"]
        self.switchbot_name = name
        self._mac = mac
        self._device = self.coordinator.switchbot_api.Switchbot(
            mac=mac, password=password, retry_count=retry_count
        )
        self._device_class = DEVICE_CLASS_SWITCH

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if not last_state:
            return
        self._state = last_state.state == "on"
        self._last_run_success = last_state.attributes["last_run_success"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        _LOGGER.info("Turn Switchbot bot on %s", self._mac)

        async with self.coordinator.api_lock:
            update_ok = await self.hass.async_add_executor_job(self._device.turn_on)

        if update_ok:
            self._last_run_success = True
        else:
            self._last_run_success = False

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        _LOGGER.info("Turn Switchbot bot off %s", self._mac)

        async with self.coordinator.api_lock:
            update_ok = await self.hass.async_add_executor_job(self._device.turn_off)

        if update_ok:
            self._last_run_success = True
        else:
            self._last_run_success = False

    @property
    def assumed_state(self) -> bool:
        """Return true if unable to access real state of entity."""
        if not self.coordinator.data[self._idx]["data"]["switchMode"]:
            return True
        return False

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self.coordinator.data[self._idx]["data"]["isOn"]

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._mac.replace(":", "")

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self.switchbot_name

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes."""
        return {
            "last_run_success": self._last_run_success,
            "MAC": self._mac,
            "switch_mode": self.coordinator.data[self._idx]["data"]["switchMode"],
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self._mac.replace(":", ""))},
            "name": self.switchbot_name,
            "model": self._model,
            "manufacturer": MANUFACTURER,
        }

    @property
    def device_class(self) -> str:
        """Device class for the sensor."""
        return self._device_class
