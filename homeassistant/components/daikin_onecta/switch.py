"""Support for Daikin AirBase zones."""

import logging
from typing import TYPE_CHECKING, override

from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .device import DaikinOnectaDevice
from .entity import DaikinManagementPointEntity
from .entity_descriptions import SWITCH_DESCRIPTIONS

if TYPE_CHECKING:
    from .coordinator import OnectaDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin switches based on config_entry."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data
    sensors = []
    supported_management_point_types = {
        "domesticHotWaterTank",
        "domesticHotWaterFlowThrough",
        "climateControl",
        "climateControlMainZone",
    }

    for device in (coordinator.data or {}).values():
        for management_point in device.device.management_points:
            management_point_type = management_point.management_point_type
            for (
                value,
                characteristic,
            ) in management_point.scalar_characteristics().items():
                values = characteristic.values or []
                if (
                    characteristic.value is not None
                    and characteristic.settable
                    and "on" in values
                    and "off" in values
                ):
                    if (
                        value == "onOffMode"
                        and management_point_type in supported_management_point_types
                    ):
                        continue
                    if (
                        value == "powerfulMode"
                        and management_point_type in supported_management_point_types
                    ):
                        continue
                    sensors.append(
                        DaikinSwitch(
                            device,
                            coordinator,
                            management_point.embedded_id,
                            management_point_type,
                            value,
                        )
                    )

    async_add_entities(sensors)


class DaikinSwitch(DaikinManagementPointEntity, ToggleEntity):
    """Represent a switchable Daikin characteristic."""

    def __init__(
        self,
        device: DaikinOnectaDevice,
        coordinator,
        embedded_id: str,
        management_point_type: str,
        value: str,
    ) -> None:
        """Initialize the switch from a device characteristic."""
        _LOGGER.info("DaikinSwitch '%s' '%s'", management_point_type, value)
        super().__init__(device, coordinator, embedded_id, management_point_type)
        self._management_point_type = management_point_type
        self._value = value
        self._attr_has_entity_name = True
        self.entity_description = SWITCH_DESCRIPTIONS.get(
            value, SwitchEntityDescription(key=value)
        )
        self._attr_unique_id = f"{self._device.id}_{self._embedded_id}_{self._value}"
        self.update_state()
        _LOGGER.info(
            "Device '%s:%s' supports sensor '%s'",
            device.name,
            self._embedded_id,
            self._value,
        )

    def update_state(self) -> None:
        """Refresh the state from the current device data."""
        self._switch_state = self.sensor_value()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        self.update_state()
        self.async_write_ha_state()

    @property
    @override
    def is_on(self):
        """Return whether the switch is on."""
        return self._switch_state == "on"

    def sensor_value(self):
        """Return the state of the switch."""
        point = self._device.management_point(self._embedded_id)
        characteristic = (
            point.scalar_characteristic(self._value) if point is not None else None
        )
        result = characteristic.value if characteristic is not None else ""
        _LOGGER.debug(
            "Device '%s' switch '%s' value '%s'", self._device.name, self._value, result
        )
        return result

    @override
    async def async_turn_on(self, **kwargs):
        """Turn the zone on."""
        if not self.is_on:
            await self._async_execute_command(
                lambda client: client.management_point(
                    self._device.id, self._embedded_id
                ).set_characteristic(
                    self._value,
                    "on",
                ),
                "switch_turn_on_failed",
            )
            point = self._device.management_point(self._embedded_id)
            characteristic = (
                point.scalar_characteristic(self._value) if point is not None else None
            )
            if characteristic is not None:
                characteristic.value = "on"
            self.update_state()
            self.async_write_ha_state()
        else:
            _LOGGER.debug(
                "Device '%s' switch '%s' request to turn on ignored because is already on",
                self._device.name,
                self._value,
            )

        return True

    @override
    async def async_turn_off(self, **kwargs):
        """Turn the zone off."""
        if self.is_on:
            await self._async_execute_command(
                lambda client: client.management_point(
                    self._device.id, self._embedded_id
                ).set_characteristic(
                    self._value,
                    "off",
                ),
                "switch_turn_off_failed",
            )
            point = self._device.management_point(self._embedded_id)
            characteristic = (
                point.scalar_characteristic(self._value) if point is not None else None
            )
            if characteristic is not None:
                characteristic.value = "off"
            self.update_state()
            self.async_write_ha_state()
        else:
            _LOGGER.debug(
                "Device '%s' switch '%s' request to turn off ignored because is already off",
                self._device.name,
                self._value,
            )

        return True
