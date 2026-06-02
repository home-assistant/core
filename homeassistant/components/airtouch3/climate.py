"""AirTouch 3 component to control AirTouch 3 Climate Devices."""

import logging
from typing import Any

from pyairtouch3 import AcMode, Aircon, AirtouchZone, ZoneStatus

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AirTouch3ConfigEntry
from .const import DOMAIN
from .coordinator import Airtouch3DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

# Map AirTouch AcMode enum to Home Assistant HVAC modes
AT_TO_HA_STATE = {
    AcMode.AUTO: HVACMode.AUTO,
    AcMode.HEAT: HVACMode.HEAT,
    AcMode.DRY: HVACMode.DRY,
    AcMode.FAN: HVACMode.FAN_ONLY,
    AcMode.COOL: HVACMode.COOL,
}

# Map Home Assistant HVAC modes to AirTouch AcMode enum values
HA_STATE_TO_AT = {value: key for key, value in AT_TO_HA_STATE.items()}

# Map AirTouch to Home Assistant Fan modes
AT_TO_HA_FAN_SPEED = {
    0: FAN_AUTO,
    1: FAN_LOW,
    2: FAN_MEDIUM,
    3: FAN_HIGH,
}

HA_FAN_SPEED_TO_AT = {value: key for key, value in AT_TO_HA_FAN_SPEED.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AirTouch3ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AirTouch 3 climate entities."""
    coordinator = config_entry.runtime_data
    aircon = coordinator.data.aircon

    entities: list[ClimateEntity] = [AirtouchAC(coordinator, aircon.ac_id)]

    entities.extend(
        AirtouchGroup(coordinator, zone.id, aircon.ac_id, zone.name)
        for zone in coordinator.data.zones.values()
    )

    _LOGGER.debug("Adding entities %s", entities)
    async_add_entities(entities)


class AirtouchClimateEntity(
    CoordinatorEntity[Airtouch3DataUpdateCoordinator], ClimateEntity
):
    """Base class for AirTouch 3 climate entities."""

    _attr_has_entity_name = True

    @property
    def aircon(self) -> Aircon:
        """Return the current AirTouch air conditioner data."""
        return self.coordinator.data.aircon


class AirtouchAC(AirtouchClimateEntity):
    """Representation of an AirTouch 3 AC unit."""

    _attr_name = None
    _attr_translation_key = "air_conditioner"
    _attr_supported_features = (
        ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1  # Only allow whole degree increments

    _attr_hvac_modes = [HVACMode.OFF, *HA_STATE_TO_AT]
    _attr_fan_modes = [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]

    def __init__(self, coordinator: Airtouch3DataUpdateCoordinator, ac_id: int) -> None:
        """Initialize the AirTouch AC unit."""
        super().__init__(coordinator)
        self.ac_id = ac_id
        self._attr_unique_id = f"{coordinator.system_id}_ac_{ac_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.system_id}_ac_{ac_id}")},
            name="AirTouch 3",
            manufacturer="Polyaire",
            model="AirTouch 3",
        )

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        fan_speed = self.aircon.fan_speed
        return AT_TO_HA_FAN_SPEED.get(fan_speed, FAN_AUTO)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.aircon.room_temperature

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        if not self.aircon.status:
            return HVACMode.OFF
        mode = self.aircon.mode
        return AT_TO_HA_STATE.get(mode, HVACMode.AUTO)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode with power control."""
        at_mode = HA_STATE_TO_AT.get(hvac_mode)

        if hvac_mode == HVACMode.OFF:
            await self.coordinator.send_command("turn_off", self.ac_id)
            _LOGGER.debug("Turning off AC %s", self.ac_id)
        elif at_mode is not None:
            await self.coordinator.send_command("set_mode", self.ac_id, at_mode.value)
            _LOGGER.debug("Setting HVAC mode of AC %s to %s", self.ac_id, hvac_mode)
            await self.coordinator.send_command("turn_on", self.ac_id)
            _LOGGER.debug("Turning on AC %s after setting mode", self.ac_id)
            self.aircon.mode = at_mode
        else:
            _LOGGER.warning("Unsupported HVAC mode: %s", hvac_mode)
            return

        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        at_fan_mode = HA_FAN_SPEED_TO_AT.get(fan_mode)
        if at_fan_mode is not None:
            await self.coordinator.send_command(
                "set_fan_speed", self.ac_id, at_fan_mode
            )
            _LOGGER.debug("Setting fan mode of AC %s to %s", self.ac_id, fan_mode)
            self.aircon.fan_speed = at_fan_mode
            self.async_write_ha_state()
        else:
            _LOGGER.warning("Unsupported fan mode: %s", fan_mode)


class AirtouchGroup(AirtouchClimateEntity):
    """Representation of an AirTouch 3 zone group.

    AirTouch exposes duct zones as groups, not independent AC units. The controller
    only supports zone on/off and target temperature commands, so Home Assistant
    represents an enabled zone as fan-only rather than a full HVAC unit.
    """

    _attr_name = None
    _attr_translation_key = "zone"
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1  # Only allow whole degree increments
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.FAN_ONLY]

    def __init__(
        self,
        coordinator: Airtouch3DataUpdateCoordinator,
        group_id: int,
        ac_id: int,
        zone_name: str,
    ) -> None:
        """Initialize the AirTouch group (zone)."""
        super().__init__(coordinator)
        self.group_id = group_id
        self.ac_id = ac_id
        self._attr_unique_id = f"{coordinator.system_id}_{ac_id}_group_{group_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.system_id}_group_{group_id}")},
            manufacturer="Polyaire",
            model="AirTouch 3",
            name=zone_name,
        )

    def _get_zone(self) -> AirtouchZone | None:
        """Fetch the zone data object for this group."""
        return self.coordinator.data.zones.get(self.group_id)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature for this group (zone)."""
        zone = self._get_zone()
        if zone and zone.sensor and zone.sensor.is_available:
            return zone.sensor.current_temperature
        return self.aircon.room_temperature or None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature for this group (zone)."""
        zone = self._get_zone()
        return zone.desired_temperature if zone else None

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the HVAC mode for the group, mapped to its on/off state."""
        zone = self._get_zone()
        if zone and zone.status == ZoneStatus.ZONE_ON:
            return HVACMode.FAN_ONLY
        return HVACMode.OFF

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature for the group (zone)."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            zone = self._get_zone()
            if zone is None:
                _LOGGER.warning("Zone %s not found", self.group_id)
                return

            current_temp = zone.desired_temperature
            diff = temperature - current_temp
            steps = abs(round(diff))
            if steps == 0:
                _LOGGER.debug(
                    "Target temperature is already close to %s",
                    temperature,
                )
                return

            inc_dec = 1 if diff > 0 else -1
            _LOGGER.debug(
                "Adjusting temperature for zone %s from %s to %s in %s step(s)",
                self.group_id,
                current_temp,
                temperature,
                steps,
            )

            for _ in range(steps):
                await self.coordinator.send_command(
                    "set_group_temperature", self.group_id, inc_dec
                )

            zone.desired_temperature = current_temp + inc_dec * steps
            self.async_write_ha_state()

            _LOGGER.debug(
                "Set target temperature for zone %s to %s",
                self.group_id,
                zone.desired_temperature,
            )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode by toggling the zone's power state as needed."""
        zone = self._get_zone()
        if not zone:
            _LOGGER.warning("Zone %s not found", self.group_id)
            return

        if hvac_mode == HVACMode.FAN_ONLY and zone.status == ZoneStatus.ZONE_OFF:
            await self.coordinator.send_command("toggle_zone", self.group_id)
            zone.status = ZoneStatus.ZONE_ON
            _LOGGER.debug(
                "Turning on group %s with FAN_ONLY mode",
                self.group_id,
            )
        elif hvac_mode == HVACMode.OFF and zone.status == ZoneStatus.ZONE_ON:
            await self.coordinator.send_command("toggle_zone", self.group_id)
            zone.status = ZoneStatus.ZONE_OFF
            _LOGGER.debug(
                "Turning off group %s with OFF mode",
                self.group_id,
            )

        self.async_write_ha_state()
