"""Base entity for Geniushub."""

from datetime import datetime, timedelta
from typing import Any, override

from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import DOMAIN, GeniusHubConfigEntry
from .const import (
    ATTR_MANUFACTURER,
    GH_DEVICE_ATTRS,
    GH_ZONE_ATTRS,
    IDENTIFIER_DEVICE,
    IDENTIFIER_ZONE,
    SERIAL_NO,
    GeniusHubServiceArgument,
)


class GeniusEntity(CoordinatorEntity):
    """Base for all Genius Hub entities."""

    _attr_should_poll = False

    def __init__(self, coordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._unique_id: str | None = None

    @override
    def _handle_coordinator_update(self) -> None:
        """Process any signals."""
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    @override
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return self._unique_id


class GeniusDevice(GeniusEntity):
    """Base for all Genius Hub devices."""

    def __init__(self, coordinator, device) -> None:
        """Initialize the Device."""
        super().__init__(coordinator)

        self._device = device
        self._unique_id = f"{coordinator.hub_uid}_device_{device.id}"
        self._last_comms: datetime | None = None
        self._state_attr = None
        self._hub = coordinator

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        attrs = {"assigned_zone": self._device.data["assignedZones"][0]["name"]}
        if self._last_comms:
            attrs["last_comms"] = self._last_comms.isoformat()

        state = dict(self._device.data["state"])
        if "_state" in self._device.data:  # only via v3 API
            state |= self._device.data["_state"]

        attrs["state"] = {
            GH_DEVICE_ATTRS[k]: v for k, v in state.items() if k in GH_DEVICE_ATTRS
        }

        return attrs

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Entity device info."""
        via_device = _get_via_device_id(
            self.hass,
            self.coordinator.config_entry,
            (DOMAIN, IDENTIFIER_ZONE.format(self._device.assigned_zone.id)),
        )

        name = f"{self._device.type.title()} {self._device.id}"
        model = f"{self._device.type} ({self._device.device_model})"

        return DeviceInfo(
            identifiers={(DOMAIN, IDENTIFIER_DEVICE.format(self._device.id))},
            via_device_id=via_device.id,
            name=name,
            manufacturer=ATTR_MANUFACTURER,
            model=model,
            serial_number=SERIAL_NO.format("Device", self._device.id),
        )

    async def async_update(self) -> None:
        """Update an entity's state data."""
        if (state := self._device.data.get("_state")) and (
            last_comms := state.get("lastComms")
        ) is not None:  # only via v3 API
            self._last_comms = dt_util.utc_from_timestamp(last_comms)


class GeniusZone(GeniusEntity):
    """Base for all Genius Hub zones."""

    def __init__(self, coordinator, zone) -> None:
        """Initialize the Zone."""
        super().__init__(coordinator)

        self._zone = zone
        self._unique_id = f"{coordinator.hub_uid}_zone_{zone.id}"
        self._hub = coordinator

    @property
    @override
    def name(self) -> str:
        """Return the name of the climate device."""
        return self._zone.name

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        status = {k: v for k, v in self._zone.data.items() if k in GH_ZONE_ATTRS}
        return {"status": status}

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Entity device info."""

        via_device = _get_via_device_id(
            self.hass, self.coordinator.config_entry, (DOMAIN, self._hub.hub_uid)
        )

        return DeviceInfo(
            identifiers={(DOMAIN, IDENTIFIER_ZONE.format(self._zone.id))},
            name=self._zone.name,
            via_device_id=via_device.id,
            manufacturer=ATTR_MANUFACTURER,
            model=f"{self._zone.data['type'].title()} Zone",
            serial_number=SERIAL_NO.format("Zone", self._zone.id),
        )


class GeniusHeatingZone(GeniusZone):
    """Base for Genius Heating Zones."""

    _max_temp: float
    _min_temp: float
    _attr_native_temperature_unit: str = UnitOfTemperature.CELSIUS

    @property
    def native_current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._zone.data.get("temperature")

    @property
    def native_target_temperature(self) -> float:
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

    async def async_set_temperature(self, **kwargs) -> None:
        """Set a new target temperature for this zone."""
        duration: timedelta = kwargs.get(
            GeniusHubServiceArgument.DURATION, timedelta(hours=1)
        )
        await self._zone.set_override(
            kwargs[GeniusHubServiceArgument.TEMPERATURE],
            kwargs.get(
                GeniusHubServiceArgument.DURATION, int(duration.total_seconds())
            ),
        )

    async def async_set_zone_mode(self, mode):
        """Set a new zone mode."""
        if mode == "footprint" and not self._zone._has_pir:  # noqa: SLF001
            raise ServiceValidationError(
                f"'{self.entity_id}' cannot support footprint mode (it has no PIR)"
            )

        await self._zone.set_mode(mode)

    async def async_set_zone_override(self, temperature, duration=timedelta(hours=1)):
        """Set a new zone override."""
        await self._zone.set_override(temperature, int(duration.total_seconds()))


def _get_via_device_id(
    hass: HomeAssistant, entry: GeniusHubConfigEntry, identifiers
) -> DeviceInfo:
    dev_reg = dr.async_get(hass)
    return dev_reg.async_get_device_by_identifier(identifiers, entry.entry_id)
