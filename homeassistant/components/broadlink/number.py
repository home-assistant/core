"""Support for Broadlink number entities."""

from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import BROADLINK_DATA, DOMAIN, DOMAINS_AND_TYPES
from .device import BroadlinkDevice
from .entity import BroadlinkEntity


@dataclass(frozen=True, kw_only=True)
class BroadlinkNumberEntityDescription(NumberEntityDescription):
    """Describes a Broadlink thermostat advanced setting."""

    data_key: str


NUMBER_TYPES: tuple[BroadlinkNumberEntityDescription, ...] = (
    BroadlinkNumberEntityDescription(
        key="min_temp",
        translation_key="min_temp",
        data_key="svl",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=5,
        native_max_value=99,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    BroadlinkNumberEntityDescription(
        key="max_temp",
        translation_key="max_temp",
        data_key="svh",
        device_class=NumberDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        native_min_value=5,
        native_max_value=99,
        native_step=1,
        mode=NumberMode.BOX,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Broadlink number entities."""
    device = hass.data[BROADLINK_DATA].devices[config_entry.entry_id]

    if device.api.type in DOMAINS_AND_TYPES[Platform.NUMBER]:
        async_add_entities(
            BroadlinkThermostatNumber(device, description)
            for description in NUMBER_TYPES
        )


class BroadlinkThermostatNumber(BroadlinkEntity, NumberEntity):
    """Representation of a Broadlink thermostat advanced setting."""

    _attr_has_entity_name = True
    entity_description: BroadlinkNumberEntityDescription

    def __init__(
        self, device: BroadlinkDevice, description: BroadlinkNumberEntityDescription
    ) -> None:
        """Initialize the number entity."""
        super().__init__(device)
        self.entity_description = description
        self._attr_unique_id = f"{device.unique_id}-{description.key}"

    @override
    def _update_state(self, data: dict[str, Any]) -> None:
        """Update the state of the entity."""
        self._attr_native_value = data.get(self.entity_description.data_key)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the value on the device."""
        async with self._device.settings_lock:
            # The device only accepts the advanced settings as a whole block, so
            # resend its current values with the one being changed replaced. Read
            # them fresh, as the coordinator data may predate a mode change.
            data = await self._device.async_request(self._device.api.get_full_status)
            settings = {
                # Register 2 holds both nibbles; get_full_status splits them.
                "loop_mode": (data["loop_mode"] << 4) | data["auto_mode"],
                "sensor": data["sensor"],
                "osv": data["osv"],
                "dif": data["dif"],
                "svh": data["svh"],
                "svl": data["svl"],
                "adj": data["room_temp_adj"],
                "fre": data["fre"],
                "poweron": data["poweron"],
            }
            settings[self.entity_description.data_key] = round(value)
            if settings["svl"] > settings["svh"]:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="setpoint_limits_inverted",
                    translation_placeholders={
                        "min_temp": str(settings["svl"]),
                        "max_temp": str(settings["svh"]),
                    },
                )
            await self._device.async_request(self._device.api.set_advanced, **settings)
        await self._coordinator.async_request_refresh()
