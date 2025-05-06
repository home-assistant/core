"""Support for Nexia switches."""

from __future__ import annotations

from typing import Any

from nexia.const import OPERATION_MODE_OFF
from nexia.roomiq import NexiaRoomIQHarmonizer
from nexia.sensor import NexiaSensor
from nexia.thermostat import NexiaThermostat
from nexia.zone import NexiaThermostatZone

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NexiaDataUpdateCoordinator
from .entity import NexiaThermostatEntity, NexiaThermostatZoneEntity
from .types import NexiaConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NexiaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches for a Nexia device."""
    coordinator = config_entry.runtime_data
    nexia_home = coordinator.nexia_home
    entities: list[SwitchEntity] = []
    room_iq_zones: dict[int, NexiaRoomIQHarmonizer] = {}
    for thermostat_id in nexia_home.get_thermostat_ids():
        thermostat: NexiaThermostat = nexia_home.get_thermostat_by_id(thermostat_id)
        if thermostat.has_emergency_heat():
            entities.append(NexiaEmergencyHeatSwitch(coordinator, thermostat))
        for zone_id in thermostat.get_zone_ids():
            zone: NexiaThermostatZone = thermostat.get_zone_by_id(zone_id)
            entities.append(NexiaHoldSwitch(coordinator, zone))
            if len(zone_sensors := zone.get_sensors()) > 1:
                entities.extend(
                    NexiaRoomIQSwitch(coordinator, zone, sensor, room_iq_zones)
                    for sensor in zone_sensors
                )

    async_add_entities(entities)
    for harmonizer in room_iq_zones.values():

        async def _stop_obj(_: Event, obj=harmonizer) -> None:
            """Run the shutdown method when preparing to stop."""
            await obj.async_shutdown()

        config_entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _stop_obj)
        )


class NexiaHoldSwitch(NexiaThermostatZoneEntity, SwitchEntity):
    """Provides Nexia hold switch support."""

    _attr_translation_key = "hold"

    def __init__(
        self, coordinator: NexiaDataUpdateCoordinator, zone: NexiaThermostatZone
    ) -> None:
        """Initialize the hold mode switch."""
        zone_id = zone.zone_id
        super().__init__(coordinator, zone, zone_id)

    @property
    def is_on(self) -> bool:
        """Return if the zone is in hold mode."""
        return self._zone.is_in_permanent_hold()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable permanent hold."""
        if self._zone.get_current_mode() == OPERATION_MODE_OFF:
            await self._zone.call_permanent_off()
        else:
            await self._zone.set_permanent_hold()
        self._signal_zone_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable permanent hold."""
        await self._zone.call_return_to_schedule()
        self._signal_zone_update()


class NexiaRoomIQSwitch(NexiaThermostatZoneEntity, SwitchEntity):
    """Provides Nexia RoomIQ sensor switch support."""

    _attr_translation_key = "room_iq_sensor"

    def __init__(
        self,
        coordinator: NexiaDataUpdateCoordinator,
        zone: NexiaThermostatZone,
        sensor: NexiaSensor,
        room_iq_zones: dict[int, NexiaRoomIQHarmonizer],
    ) -> None:
        """Initialize the RoomIQ sensor switch."""
        super().__init__(coordinator, zone, f"{sensor.id}_room_iq_sensor")
        self._attr_translation_placeholders = {"sensor_name": sensor.name}
        self._sensor_id = sensor.id
        self._harmonizer = room_iq_zones.setdefault(
            zone.zone_id,
            NexiaRoomIQHarmonizer(
                zone, coordinator.async_refresh, self._signal_zone_update
            ),
        )

    @property
    def is_on(self) -> bool:
        """Return if the sensor is part of the zone average temperature."""
        if self._harmonizer.request_pending():
            return self._sensor_id in self._harmonizer.selected_sensor_ids

        included = self._zone.get_sensor_by_id(self._sensor_id).weight > 0.0
        # Keep our collection of selected RoomIQ sensors up to date
        if included:
            self._harmonizer.selected_sensor_ids.add(self._sensor_id)
        else:
            self._harmonizer.selected_sensor_ids.discard(self._sensor_id)
        return included

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Include this sensor."""
        self._harmonizer.trigger_add_sensor(self._sensor_id)
        self._signal_zone_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Remove this sensor."""
        self._harmonizer.trigger_remove_sensor(self._sensor_id)
        self._signal_zone_update()


class NexiaEmergencyHeatSwitch(NexiaThermostatEntity, SwitchEntity):
    """Provides Nexia emergency heat switch support."""

    _attr_translation_key = "emergency_heat"

    def __init__(
        self, coordinator: NexiaDataUpdateCoordinator, thermostat: NexiaThermostat
    ) -> None:
        """Initialize the emergency heat mode switch."""
        super().__init__(
            coordinator,
            thermostat,
            unique_id=f"{thermostat.thermostat_id}_emergency_heat",
        )

    @property
    def is_on(self) -> bool:
        """Return if the zone is in hold mode."""
        return self._thermostat.is_emergency_heat_active()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable permanent hold."""
        await self._thermostat.set_emergency_heat(True)
        self._signal_thermostat_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable permanent hold."""
        await self._thermostat.set_emergency_heat(False)
        self._signal_thermostat_update()
