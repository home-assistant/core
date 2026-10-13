"""Support for Daikin Onecta switches."""

from typing import TYPE_CHECKING, Any, override

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DaikinOnectaConfigEntry
from .device import DaikinOnectaDevice
from .entity import DaikinManagementPointEntity
from .entity_descriptions import SWITCH_DESCRIPTIONS

PARALLEL_UPDATES = 1

if TYPE_CHECKING:
    from .coordinator import OnectaDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DaikinOnectaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin switches based on config_entry."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data
    sensors: list[DaikinSwitch] = []
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
                    characteristic.settable
                    and "on" in values
                    and "off" in values
                    and (description := SWITCH_DESCRIPTIONS.get(value)) is not None
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
                            description,
                            value,
                        )
                    )

    async_add_entities(sensors)


class DaikinSwitch(DaikinManagementPointEntity, SwitchEntity):
    """Represent a switchable Daikin characteristic."""

    def __init__(
        self,
        device: DaikinOnectaDevice,
        coordinator: OnectaDataUpdateCoordinator,
        embedded_id: str,
        description: SwitchEntityDescription,
        value: str,
    ) -> None:
        """Initialize the switch from a device characteristic."""
        super().__init__(device, coordinator, embedded_id)
        self._value = value
        self.entity_description = description
        self._attr_unique_id = f"{self._device.id}_{self._embedded_id}_{self._value}"
        self.update_state()

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
    def is_on(self) -> bool | None:
        """Return whether the switch is on."""
        if self._switch_state is None:
            return None
        return self._switch_state == "on"

    def sensor_value(self) -> str | None:
        """Return the state of the switch."""
        point = self._device.management_point(self._embedded_id)
        characteristic = (
            point.scalar_characteristic(self._value) if point is not None else None
        )
        result = characteristic.value if characteristic is not None else None
        return result if isinstance(result, str) else None

    @property
    @override
    def available(self) -> bool:
        """Return whether the characteristic still exposes writable on/off values."""
        if not super().available:
            return False
        point = self._device.management_point(self._embedded_id)
        characteristic = (
            point.scalar_characteristic(self._value) if point is not None else None
        )
        return bool(
            characteristic is not None
            and characteristic.settable
            and {"on", "off"}.issubset(characteristic.values or [])
        )

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the zone on."""
        if self.is_on is None:
            self._raise_service_validation_error("switch_state_unavailable")
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
            self.coordinator.async_update_listeners()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the zone off."""
        if self.is_on is None:
            self._raise_service_validation_error("switch_state_unavailable")
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
            self.coordinator.async_update_listeners()
