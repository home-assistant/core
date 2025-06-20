"""EHEIM Digital select entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from eheimdigital.classic_vario import EheimDigitalClassicVario
from eheimdigital.device import EheimDigitalDevice
from eheimdigital.types import FilterMode

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EheimDigitalConfigEntry, EheimDigitalUpdateCoordinator
from .entity import EheimDigitalEntity, exception_handler

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class EheimDigitalSelectDescription[_DeviceT: EheimDigitalDevice](
    SelectEntityDescription
):
    """Class describing EHEIM Digital select entities."""

    value_fn: Callable[[_DeviceT], str | None]
    set_value_fn: Callable[[_DeviceT, str], Awaitable[None]]


CLASSICVARIO_DESCRIPTIONS: tuple[
    EheimDigitalSelectDescription[EheimDigitalClassicVario], ...
] = (
    EheimDigitalSelectDescription[EheimDigitalClassicVario](
        key="filter_mode",
        translation_key="filter_mode",
        value_fn=(
            lambda device: device.filter_mode.name.lower()
            if device.filter_mode is not None
            else None
        ),
        set_value_fn=(
            lambda device, value: device.set_filter_mode(FilterMode[value.upper()])
        ),
        options=[name.lower() for name in FilterMode.__members__],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EheimDigitalConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the callbacks for the coordinator so select entities can be added as devices are found."""
    coordinator = entry.runtime_data

    def async_setup_device_entities(
        device_address: dict[str, EheimDigitalDevice],
    ) -> None:
        """Set up the number entities for one or multiple devices."""
        entities: list[EheimDigitalSelect[Any]] = []
        for device in device_address.values():
            if isinstance(device, EheimDigitalClassicVario):
                entities.extend(
                    EheimDigitalSelect[EheimDigitalClassicVario](
                        coordinator, device, description
                    )
                    for description in CLASSICVARIO_DESCRIPTIONS
                )

        async_add_entities(entities)

    coordinator.add_platform_callback(async_setup_device_entities)
    async_setup_device_entities(coordinator.hub.devices)


class EheimDigitalSelect[_DeviceT: EheimDigitalDevice](
    EheimDigitalEntity[_DeviceT], SelectEntity
):
    """Represent an EHEIM Digital select entity."""

    entity_description: EheimDigitalSelectDescription[_DeviceT]

    def __init__(
        self,
        coordinator: EheimDigitalUpdateCoordinator,
        device: _DeviceT,
        description: EheimDigitalSelectDescription[_DeviceT],
    ) -> None:
        """Initialize an EHEIM Digital select entity."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_address}_{description.key}"

    @override
    @exception_handler
    async def async_select_option(self, option: str) -> None:
        return await self.entity_description.set_value_fn(self._device, option)

    @override
    def _async_update_attrs(self) -> None:
        self._attr_current_option = self.entity_description.value_fn(self._device)
