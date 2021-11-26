"""Support for Switchbot bot."""
from __future__ import annotations

import logging
from typing import Any

from switchbot import Switchbot  # pylint: disable=import-error
import voluptuous as vol

from homeassistant.components.switch import (
    DEVICE_CLASS_SWITCH,
    PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SENSOR_TYPE,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import ATTR_BOT, CONF_RETRY_COUNT, DATA_COORDINATOR, DEFAULT_NAME, DOMAIN
from .coordinator import SwitchbotDataUpdateCoordinator
from .entity import SwitchbotEntity

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

    async_add_entities(
        [
            SwitchBotBotEntity(
                coordinator,
                entry.unique_id,
                entry.data[CONF_MAC],
                entry.data[CONF_NAME],
                coordinator.switchbot_api.Switchbot(
                    mac=entry.data[CONF_MAC],
                    password=entry.data.get(CONF_PASSWORD),
                    retry_count=entry.options[CONF_RETRY_COUNT],
                ),
            )
        ]
    )


class SwitchBotBotEntity(SwitchbotEntity, SwitchEntity, RestoreEntity):
    """Representation of a Switchbot."""

    coordinator: SwitchbotDataUpdateCoordinator
    _attr_device_class = DEVICE_CLASS_SWITCH

    def __init__(
        self,
        coordinator: SwitchbotDataUpdateCoordinator,
        idx: str | None,
        mac: str,
        name: str,
        device: Switchbot,
    ) -> None:
        """Initialize the Switchbot."""
        super().__init__(coordinator, idx, mac, name)
        self._attr_unique_id = idx
        self._device = device

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        if not (last_state := await self.async_get_last_state()):
            return
        self._attr_is_on = last_state.state == STATE_ON
        self._last_run_success = last_state.attributes["last_run_success"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        _LOGGER.info("Turn Switchbot bot on %s", self._mac)

        async with self.coordinator.api_lock:
            self._last_run_success = bool(
                await self.hass.async_add_executor_job(self._device.turn_on)
            )
            if self._last_run_success:
                self._attr_is_on = True

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        _LOGGER.info("Turn Switchbot bot off %s", self._mac)

        async with self.coordinator.api_lock:
            self._last_run_success = bool(
                await self.hass.async_add_executor_job(self._device.turn_off)
            )
            if self._last_run_success:
                self._attr_is_on = False

    @property
    def assumed_state(self) -> bool:
        """Return true if unable to access real state of entity."""
        if not self.data["data"]["switchMode"]:
            return True
        return False

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        if not self.data["data"]["switchMode"]:
            return self._attr_is_on
        return self.data["data"]["isOn"]

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        return {
            **super().extra_state_attributes,
            "switch_mode": self.data["data"]["switchMode"],
        }
