"""Support for Daikin Onecta switches."""

from typing import TYPE_CHECKING, Any, override

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DaikinOnectaConfigEntry
from .device import DaikinOnectaDevice
from .discovery import scalar_characteristics_for_platform, scalar_platform
from .entity import (
    DaikinManagementPointEntity,
    add_entities_on_coordinator_update,
    management_point_unique_id,
)
from .entity_metadata import (
    ENTITY_METADATA,
    SWITCH_TRANSLATION_KEYS,
    entity_description_kwargs,
)

PARALLEL_UPDATES = 1

SWITCH_DESCRIPTIONS = {
    metadata.key: SwitchEntityDescription(
        key=metadata.key, **entity_description_kwargs(metadata)
    )
    for metadata in ENTITY_METADATA
    if metadata.translation_key in SWITCH_TRANSLATION_KEYS
}

if TYPE_CHECKING:
    from .coordinator import OnectaDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DaikinOnectaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin switches based on config_entry."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data
    add_entities_on_coordinator_update(
        config_entry,
        coordinator,
        async_add_entities,
        lambda added: _create_switches(coordinator, added),
    )


def _create_switches(
    coordinator: OnectaDataUpdateCoordinator,
    added_unique_ids: set[str],
) -> list[DaikinSwitch]:
    """Create supported switches from the current cloud model."""
    sensors: list[DaikinSwitch] = []

    for device in (coordinator.data or {}).values():
        for management_point in device.device.management_points:
            for value, _characteristic in scalar_characteristics_for_platform(
                management_point, Platform.SWITCH
            ):
                unique_id = management_point_unique_id(
                    device.id, management_point.embedded_id, value
                )
                if unique_id in added_unique_ids:
                    continue
                sensors.append(
                    DaikinSwitch(
                        device,
                        coordinator,
                        management_point.embedded_id,
                        SWITCH_DESCRIPTIONS[value],
                        value,
                    )
                )

    return sensors


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
        self._attr_unique_id = management_point_unique_id(
            self._device.id, self._embedded_id, self._value
        )
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
            point.characteristic(self._value) if point is not None else None
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
        if point is None:
            return False
        characteristic = point.characteristic(self._value)
        return bool(
            characteristic is not None
            and scalar_platform(
                self._value, characteristic, point.management_point_type
            )
            is Platform.SWITCH
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
                point.characteristic(self._value) if point is not None else None
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
                point.characteristic(self._value) if point is not None else None
            )
            if characteristic is not None:
                characteristic.value = "off"
            self.update_state()
            self.coordinator.async_update_listeners()
