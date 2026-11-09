"""Valve platform for RainMachine irrigation zones."""

from dataclasses import dataclass
from typing import override

from regenmaschine.errors import RainMachineError

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityDescription,
    ValveEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RainMachineConfigEntry, RainMachineData
from .const import (
    CONF_ALLOW_INACTIVE_ZONES_TO_RUN,
    CONF_DEFAULT_ZONE_RUN_TIME,
    CONF_USE_APP_RUN_TIMES,
    DATA_PROVISION_SETTINGS,
    DATA_ZONES,
)
from .entity import RainMachineEntity, RainMachineEntityDescription
from .services import async_update_programs_and_zones


@dataclass(frozen=True, kw_only=True)
class RainMachineValveDescription(ValveEntityDescription, RainMachineEntityDescription):
    """Describe a RainMachine irrigation-zone valve."""

    uid: int


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RainMachineConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up RainMachine irrigation zones as water valves."""
    data = entry.runtime_data
    coordinator = data.coordinators[DATA_ZONES]
    async_add_entities(
        RainMachineZoneValve(
            entry,
            data,
            RainMachineValveDescription(
                key=f"zone_{uid}",
                name=zone["name"].capitalize(),
                api_category=DATA_ZONES,
                device_class=ValveDeviceClass.WATER,
                uid=uid,
            ),
        )
        for uid, zone in coordinator.data.items()
    )


class RainMachineZoneValve(RainMachineEntity, ValveEntity):
    """Represent a RainMachine irrigation zone as a water valve."""

    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
    _attr_reports_position = False
    entity_description: RainMachineValveDescription

    def __init__(
        self,
        entry: RainMachineConfigEntry,
        data: RainMachineData,
        description: RainMachineValveDescription,
    ) -> None:
        """Initialize a RainMachine irrigation-zone valve."""
        super().__init__(entry, data, description)
        self._entry = entry

    @callback
    def _update_activities(self) -> None:
        """Refresh linked program and zone state."""
        self.hass.async_create_task(
            async_update_programs_and_zones(self.hass, self._entry)
        )

    def _ensure_zone_can_run(self) -> None:
        """Reject opening a disabled RainMachine zone unless explicitly allowed."""
        if (
            not self._entry.options[CONF_ALLOW_INACTIVE_ZONES_TO_RUN]
            and not self.coordinator.data[self.entity_description.uid]["active"]
        ):
            raise HomeAssistantError(f"Cannot open an inactive zone: {self.name}")

    def _default_duration(self) -> int:
        """Return the configured run time for this zone."""
        if self._entry.options[CONF_USE_APP_RUN_TIMES]:
            provision_data = self._data.coordinators[DATA_PROVISION_SETTINGS].data
            zone_durations = provision_data.get("system", {}).get("zoneDuration")
            if zone_durations:
                zone_index = list(self.coordinator.data).index(
                    self.entity_description.uid
                )
                if zone_index < len(zone_durations):
                    return int(zone_durations[zone_index])
        return int(self._entry.options[CONF_DEFAULT_ZONE_RUN_TIME])

    async def _async_open(self, duration: int) -> None:
        """Open the zone for a specific number of seconds."""
        self._ensure_zone_can_run()
        try:
            await self._data.controller.zones.start(
                self.entity_description.uid, duration
            )
        except RainMachineError as err:
            raise HomeAssistantError(f"Error while opening {self.name}: {err}") from err
        self._update_activities()

    @override
    async def async_open_valve(self) -> None:
        """Open the irrigation zone using its configured run time."""
        await self._async_open(self._default_duration())

    @override
    async def async_close_valve(self) -> None:
        """Close the irrigation zone."""
        try:
            await self._data.controller.zones.stop(self.entity_description.uid)
        except RainMachineError as err:
            raise HomeAssistantError(f"Error while closing {self.name}: {err}") from err
        self._update_activities()

    async def async_start_zone(self, *, zone_run_time: int) -> None:
        """Start the zone for an explicit duration."""
        await self._async_open(zone_run_time)

    async def async_stop_zone(self) -> None:
        """Stop the zone."""
        await self.async_close_valve()

    @callback
    @override
    def update_from_latest_data(self) -> None:
        """Update the valve state."""
        self._attr_is_closed = not bool(
            self.coordinator.data[self.entity_description.uid]["state"]
        )
