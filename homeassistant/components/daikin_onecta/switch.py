"""Support for Daikin Onecta switches."""

from typing import Any, Literal, override

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ENTITY_METADATA, SWITCH_TRANSLATION_KEYS, entity_description_kwargs
from .coordinator import DaikinOnectaConfigEntry, OnectaDataUpdateCoordinator
from .device import DaikinOnectaDevice
from .discovery import scalar_characteristics_for_platform
from .entity import (
    DaikinManagementPointEntity,
    EntityIdChecker,
    add_entities_on_coordinator_update,
    iter_management_points,
)
from .utils import is_on_off_value, management_point_unique_id

PARALLEL_UPDATES = 1

SWITCH_DESCRIPTIONS = {
    metadata.key: SwitchEntityDescription(
        key=metadata.key, **entity_description_kwargs(metadata)
    )
    for metadata in ENTITY_METADATA
    if metadata.translation_key in SWITCH_TRANSLATION_KEYS
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DaikinOnectaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin switches based on config_entry."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data
    add_entities_on_coordinator_update(
        hass,
        config_entry,
        coordinator,
        async_add_entities,
        lambda is_known: _create_switches(coordinator, is_known),
    )


def _create_switches(
    coordinator: OnectaDataUpdateCoordinator,
    is_known: EntityIdChecker,
) -> list[DaikinSwitch]:
    """Create supported switches from the current cloud model."""
    switches: list[DaikinSwitch] = []

    for device, management_point in iter_management_points(coordinator):
        for value, _characteristic in scalar_characteristics_for_platform(
            management_point,
            Platform.SWITCH,
            gateway_online=device.gateway_online,
        ):
            unique_id = management_point_unique_id(
                device.id, management_point.embedded_id, value
            )
            if is_known(Platform.SWITCH, unique_id):
                continue
            switches.append(
                DaikinSwitch(
                    device,
                    coordinator,
                    management_point.embedded_id,
                    SWITCH_DESCRIPTIONS[value],
                )
            )
    return switches


class DaikinSwitch(DaikinManagementPointEntity, SwitchEntity):
    """Represent a switchable Daikin characteristic."""

    def __init__(
        self,
        device: DaikinOnectaDevice,
        coordinator: OnectaDataUpdateCoordinator,
        embedded_id: str,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch from a device characteristic."""
        super().__init__(device, coordinator, embedded_id)
        self.entity_description = description
        self._attr_unique_id = management_point_unique_id(
            self._device_id, self._embedded_id, self.entity_description.key
        )
        self.update_state()

    @override
    def update_state(self) -> None:
        """Refresh the state and platform exposure from current device data."""
        characteristic = self._characteristic(self.entity_description.key)
        result = characteristic.value if characteristic is not None else None
        self._attr_is_on = (
            True if result == "on" else False if result == "off" else None
        )
        self._is_exposed_on_platform = (
            characteristic is not None
            and characteristic.settable
            and is_on_off_value(characteristic.values)
            and self._characteristic_exposed_on(
                self.entity_description.key, Platform.SWITCH
            )
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether the characteristic still exposes writable on/off values."""
        return super().available and self._is_exposed_on_platform

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_set_state("on", "switch_turn_on_failed")

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_set_state("off", "switch_turn_off_failed")

    async def _async_set_state(
        self, state: Literal["on", "off"], translation_key: str
    ) -> None:
        """Set a switch characteristic and publish its successful state."""
        if self.is_on is None:
            self._raise_service_validation_error("switch_state_unavailable")
        requested_state = state == "on"
        if self.is_on == requested_state:
            return
        await self._async_execute_command(
            lambda client: client.management_point(
                self._device_id, self._embedded_id
            ).set_characteristic(self.entity_description.key, state),
            translation_key,
        )
        characteristic = self._characteristic(self.entity_description.key)
        if characteristic is not None:
            characteristic.value = state
        self._publish_write_update()
