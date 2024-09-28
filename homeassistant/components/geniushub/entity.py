"""Base entity for Geniushub."""

from datetime import datetime, timedelta
from typing import Any

from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from . import (
    ATTR_DURATION,
    ATTR_ZONE_MODE,
    DOMAIN,
    SVC_SET_ZONE_OVERRIDE,
    GeniusHubCoordinator,
)

# temperature is repeated here, as it gives access to high-precision temps
GH_ZONE_ATTRS = ["mode", "temperature", "type", "occupied", "override"]
GH_DEVICE_ATTRS = {
    "luminance": "luminance",
    "measuredTemperature": "measured_temperature",
    "occupancyTrigger": "occupancy_trigger",
    "setback": "setback",
    "setTemperature": "set_temperature",
    "wakeupInterval": "wakeup_interval",
}


class GeniusEntity(CoordinatorEntity[GeniusHubCoordinator]):
    """Base for all Genius Hub entities."""


class GeniusDevice(GeniusEntity):
    """Base for all Genius Hub devices."""

    def __init__(self, coordinator: GeniusHubCoordinator, device) -> None:
        """Initialize the Device."""
        super().__init__(coordinator)

        self._device = device
        self._attr_unique_id = f"{coordinator.unique_id}_device_{device.id}"
        self._last_comms: datetime | None = None
        self._state_attr = None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        attrs = {}
        attrs["assigned_zone"] = self._device.data["assignedZones"][0]["name"]
        if self._last_comms:
            attrs["last_comms"] = self._last_comms.isoformat()

        state = dict(self._device.data["state"])
        if "_state" in self._device.data:  # only via v3 API
            state.update(self._device.data["_state"])

        attrs["state"] = {
            GH_DEVICE_ATTRS[k]: v for k, v in state.items() if k in GH_DEVICE_ATTRS
        }

        return attrs

    def _handle_coordinator_update(self) -> None:
        """Update an entity's state data."""
        if "_state" in self._device.data:  # only via v3 API
            self._last_comms = dt_util.utc_from_timestamp(
                self._device.data["_state"]["lastComms"]
            )
        super()._handle_coordinator_update()


class GeniusZone(GeniusEntity):
    """Base for all Genius Hub zones."""

    def __init__(self, coordinator: GeniusHubCoordinator, zone) -> None:
        """Initialize the Zone."""
        super().__init__(coordinator)

        self._zone = zone
        self._attr_unique_id = f"{coordinator.unique_id}_zone_{zone.id}"

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, DOMAIN, self._handle_service_call)
        )

    async def _handle_service_call(self, payload: dict) -> None:
        """Process any signals."""
        if payload["unique_id"] != self._attr_unique_id:
            return

        if payload["service"] == SVC_SET_ZONE_OVERRIDE:
            temperature = round(payload["data"][ATTR_TEMPERATURE] * 10) / 10
            duration = payload["data"].get(ATTR_DURATION, timedelta(hours=1))

            await self._zone.set_override(temperature, int(duration.total_seconds()))
            return

        mode = payload["data"][ATTR_ZONE_MODE]

        if mode == "footprint" and not self._zone._has_pir:  # noqa: SLF001
            raise TypeError(
                f"'{self.entity_id}' cannot support footprint mode (it has no PIR)"
            )

        await self._zone.set_mode(mode)

    @property
    def name(self) -> str:
        """Return the name of the climate device."""
        return self._zone.name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        status = {k: v for k, v in self._zone.data.items() if k in GH_ZONE_ATTRS}
        return {"status": status}


class GeniusHeatingZone(GeniusZone):
    """Base for Genius Heating Zones."""

    _max_temp: float
    _min_temp: float

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._zone.data.get("temperature")

    @property
    def target_temperature(self) -> float:
        """Return the temperature we try to reach."""
        return self._zone.data["setpoint"]

    @property
    def min_temp(self) -> float:
        """Return max valid temperature that can be set."""
        return self._min_temp

    @property
    def max_temp(self) -> float:
        """Return max valid temperature that can be set."""
        return self._max_temp

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    async def async_set_temperature(self, **kwargs) -> None:
        """Set a new target temperature for this zone."""
        await self._zone.set_override(
            kwargs[ATTR_TEMPERATURE], kwargs.get(ATTR_DURATION, 3600)
        )
