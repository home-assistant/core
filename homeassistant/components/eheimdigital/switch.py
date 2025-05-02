"""EHEIM Digital switches."""

from typing import Any, override

from eheimdigital.classic_vario import EheimDigitalClassicVario
from eheimdigital.device import EheimDigitalDevice

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EheimDigitalConfigEntry, EheimDigitalUpdateCoordinator
from .entity import EheimDigitalEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EheimDigitalConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the callbacks for the coordinator so switches can be added as devices are found."""
    coordinator = entry.runtime_data

    def async_setup_device_entities(
        device_address: dict[str, EheimDigitalDevice],
    ) -> None:
        """Set up the switch entities for one or multiple devices."""
        entities: list[SwitchEntity] = []
        for device in device_address.values():
            if isinstance(device, EheimDigitalClassicVario):
                entities.append(EheimDigitalClassicVarioSwitch(coordinator, device))  # noqa: PERF401

        async_add_entities(entities)

    coordinator.add_platform_callback(async_setup_device_entities)
    async_setup_device_entities(coordinator.hub.devices)


class EheimDigitalClassicVarioSwitch(
    EheimDigitalEntity[EheimDigitalClassicVario], SwitchEntity
):
    """Represent an EHEIM Digital classicVARIO switch entity."""

    _attr_translation_key = "filter_active"
    _attr_name = None

    def __init__(
        self,
        coordinator: EheimDigitalUpdateCoordinator,
        device: EheimDigitalClassicVario,
    ) -> None:
        """Initialize an EHEIM Digital classicVARIO switch entity."""
        super().__init__(coordinator, device)
        self._attr_unique_id = device.mac_address
        self._async_update_attrs()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.set_active(active=False)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._device.set_active(active=True)

    @override
    def _async_update_attrs(self) -> None:
        self._attr_is_on = self._device.is_active
