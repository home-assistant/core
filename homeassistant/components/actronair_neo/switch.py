"""Switch platform for Actron Neo integration."""

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .device import ACZone

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Actron Neo switches."""
    # Extract API and coordinator from hass.data
    instance = config_entry.runtime_data
    api = instance.api
    coordinator = instance.coordinator
    serial_number = instance.serial_number
    ac_unit = instance.ac_unit

    # Fetch the status and create ZoneSwitches
    status = coordinator.data
    zones = status.get("RemoteZoneInfo", [])
    entities: list[SwitchEntity] = []

    # Create a switch for the continuous fan
    entities.append(ContinuousFanSwitch(api, coordinator, serial_number, ac_unit))

    for zone_number, zone in enumerate(zones, start=1):
        if zone["NV_Exists"]:
            zone_name = zone["NV_Title"]
            ac_zone = ACZone(ac_unit, zone_number, zone_name)
            entities.append(ZoneSwitch(api, coordinator, serial_number, ac_zone))

    # Add all switches
    async_add_entities(entities)


class ContinuousFanSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of the Actron Air Neo continuous fan switch."""

    _attr_has_entity_name = True
    _attr_translation_key = "continuous_fan"

    def __init__(self, api, coordinator, serial_number, ac_unit) -> None:
        """Initialize the continuous fan switch."""
        super().__init__(coordinator)
        self._api = api
        self._serial_number = serial_number
        self._ac_unit = ac_unit
        self._attr_name = "Continuous Fan"
        self._attr_unique_id = (
            f"{DOMAIN}_{self._serial_number}_switch_{self._attr_name}"
        )
        self._is_on = self.is_on

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return self._ac_unit.device_info

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        status = self.coordinator.data
        if status:
            fan_mode = status.get("UserAirconSettings", {}).get("FanMode", "")
            return fan_mode.endswith("+CONT")
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the continuous fan on."""
        self._is_on = True
        self.async_write_ha_state()

        status = self.coordinator.data
        if status:
            fan_mode = status.get("UserAirconSettings", {}).get("FanMode", "")
            if fan_mode:
                new_fan_mode = f"{fan_mode.replace('+CONT', '')}+CONT"
                await self._api.set_fan_mode(
                    serial_number=self._serial_number, fan_mode=new_fan_mode
                )
                await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the continuous fan off."""
        self._is_on = False
        self.async_write_ha_state()

        status = self.coordinator.data
        if status:
            fan_mode = status.get("UserAirconSettings", {}).get("FanMode", "")
            if fan_mode:
                new_fan_mode = fan_mode.replace("+CONT", "")
                await self._api.set_fan_mode(
                    serial_number=self._serial_number, fan_mode=new_fan_mode
                )
                await self.coordinator.async_request_refresh()


class ZoneSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a zone switch."""

    _attr_has_entity_name = True
    _attr_translation_key = "zone_enabled"

    def __init__(self, api, coordinator, serial_number, ac_zone) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._api = api
        self._serial_number = serial_number
        self._zone_number = ac_zone.zone_number
        self._attr_translation_placeholders = {"zone_number": self._zone_number}
        self._ac_zone = ac_zone
        self._attr_name = f"Zone {self._zone_number} Enabled"
        self._attr_unique_id = (
            f"{DOMAIN}_{self._serial_number}_switch_{self._attr_name}"
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return self._ac_zone.device_info

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        status = self.coordinator.data
        if status:
            enabled_zones = status.get("UserAirconSettings", {}).get("EnabledZones", [])
            if isinstance(enabled_zones, list):
                try:
                    return enabled_zones[self._zone_number - 1]
                except IndexError:
                    _LOGGER.error(
                        "Zone number %s out of range for EnabledZones: %s",
                        self._zone_number,
                        enabled_zones,
                    )
            else:
                _LOGGER.error("EnabledZones is not a list: %s", enabled_zones)
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the zone on."""
        await self._api.set_zone(
            serial_number=self._serial_number,
            zone_number=self._zone_number,
            is_enabled=True,
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the zone off."""
        await self._api.set_zone(
            serial_number=self._serial_number,
            zone_number=self._zone_number,
            is_enabled=False,
        )
        await self.coordinator.async_request_refresh()

    async def async_update(self) -> None:
        """Fetch the latest data and refresh state."""
        _LOGGER.debug("Updating Zone %s state from coordinator", self._zone_number)
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()
