"""Creates Homewizard Energy switch entities."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import (
    DEVICE_CLASS_OUTLET,
    DEVICE_CLASS_SWITCH,
    SwitchEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, CONF_STATE, ENTITY_CATEGORY_CONFIG
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_POWER_ON,
    ATTR_SWITCHLOCK,
    CONF_API,
    CONF_MODEL,
    CONF_SW_VERSION,
    COORDINATOR,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches."""

    energy_api = hass.data[DOMAIN][entry.data["unique_id"]][CONF_API]
    coordinator = hass.data[DOMAIN][entry.data["unique_id"]][COORDINATOR]

    if energy_api.state is not None:
        async_add_entities(
            [
                HWEnergyMainSwitchEntity(
                    coordinator, entry.data, ATTR_POWER_ON, energy_api
                ),
                HWEnergySwitchLockEntity(
                    coordinator, entry.data, ATTR_SWITCHLOCK, energy_api
                ),
            ]
        )


class HWEnergySwitchEntity(CoordinatorEntity, SwitchEntity):
    """Representation switchable entity."""

    unique_id = None

    def __init__(self, coordinator, entry_data, key, api) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry_data = entry_data
        self.api = api

        # Config attributes
        self.unique_id = "{}_{}".format(entry_data["unique_id"], key)
        self.data_type = key

    @property
    def data(self) -> dict[str, Any]:
        """Return data from DataUpdateCoordinator."""
        return self.coordinator.data

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        return {
            "name": self.entry_data["custom_name"],
            "manufacturer": "HomeWizard",
            "sw_version": self.data[CONF_SW_VERSION],
            "model": self.data[CONF_MODEL],
            "identifiers": {(DOMAIN, self.data[CONF_ID])},
        }

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.data[CONF_STATE][self.data_type]


class HWEnergyMainSwitchEntity(HWEnergySwitchEntity):
    """Representation of the main power switch."""

    name = None

    def __init__(self, coordinator, entry_data, key, api) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, entry_data, key, api)

        # Config attributes
        self.name = entry_data["custom_name"]

    @property
    def device_class(self) -> str | None:
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return DEVICE_CLASS_OUTLET

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.api.state.set(power_on=True)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.api.state.set(power_on=False)
        await self.coordinator.async_refresh()


class HWEnergySwitchLockEntity(HWEnergySwitchEntity):
    """Representation of the switch-lock configuration."""

    name = None

    def __init__(self, coordinator, entry_data, key, api) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, entry_data, key, api)

        # Config attributes
        self.name = "{} Switch Lock".format(entry_data["custom_name"])

    @property
    def device_class(self) -> str | None:
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return DEVICE_CLASS_SWITCH

    @property
    def entity_category(self) -> str | None:
        """Return the entity category, if any."""
        return ENTITY_CATEGORY_CONFIG

    @property
    def icon(self) -> str | None:
        """Return a representative icon."""
        return "mdi:lock"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn switch-lock on."""
        await self.api.state.set(switch_lock=True)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn switch-lock off."""
        await self.api.state.set(switch_lock=False)
        await self.coordinator.async_refresh()
