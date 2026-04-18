"""EHEIM Digital switches."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from eheimdigital.classic_vario import EheimDigitalClassicVario
from eheimdigital.device import EheimDigitalDevice
from eheimdigital.filter import EheimDigitalFilter
from eheimdigital.reeflex import EheimDigitalReeflexUV

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EheimDigitalConfigEntry, EheimDigitalUpdateCoordinator
from .entity import EheimDigitalEntity, exception_handler

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class EheimDigitalSwitchDescription[_DeviceT: EheimDigitalDevice](
    SwitchEntityDescription
):
    """Class describing EHEIM Digital switch entities."""

    is_on_fn: Callable[[_DeviceT], bool]
    set_fn: Callable[[_DeviceT, bool], Awaitable[None]]


REEFLEX_DESCRIPTIONS: tuple[
    EheimDigitalSwitchDescription[EheimDigitalReeflexUV], ...
] = (
    EheimDigitalSwitchDescription[EheimDigitalReeflexUV](
        key="active",
        name=None,
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda device: device.is_active,
        set_fn=lambda device, value: device.set_active(active=value),
    ),
    EheimDigitalSwitchDescription[EheimDigitalReeflexUV](
        key="pause",
        translation_key="pause",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda device: device.pause,
        set_fn=lambda device, value: device.set_pause(pause=value),
    ),
    EheimDigitalSwitchDescription[EheimDigitalReeflexUV](
        key="booster",
        translation_key="booster",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda device: device.booster,
        set_fn=lambda device, value: device.set_booster(active=value),
    ),
    EheimDigitalSwitchDescription[EheimDigitalReeflexUV](
        key="expert",
        translation_key="expert",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda device: device.expert,
        set_fn=lambda device, value: device.set_expert(active=value),
    ),
)


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
            if isinstance(device, (EheimDigitalClassicVario, EheimDigitalFilter)):
                entities.append(EheimDigitalFilterSwitch(coordinator, device))
            if isinstance(device, EheimDigitalReeflexUV):
                entities.extend(
                    EheimDigitalSwitch[EheimDigitalReeflexUV](
                        coordinator, device, description
                    )
                    for description in REEFLEX_DESCRIPTIONS
                )

        async_add_entities(entities)

    coordinator.add_platform_callback(async_setup_device_entities)
    async_setup_device_entities(coordinator.hub.devices)


class EheimDigitalSwitch[_DeviceT: EheimDigitalDevice](
    EheimDigitalEntity[_DeviceT], SwitchEntity
):
    """Represent a EHEIM Digital switch entity."""

    entity_description: EheimDigitalSwitchDescription[_DeviceT]

    def __init__(
        self,
        coordinator: EheimDigitalUpdateCoordinator,
        device: _DeviceT,
        description: EheimDigitalSwitchDescription[_DeviceT],
    ) -> None:
        """Initialize an EHEIM Digital switch entity."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_address}_{description.key}"

    @exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        return await self.entity_description.set_fn(self._device, True)

    @exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        return await self.entity_description.set_fn(self._device, False)

    @override
    def _async_update_attrs(self) -> None:
        self._attr_is_on = self.entity_description.is_on_fn(self._device)


class EheimDigitalFilterSwitch(
    EheimDigitalEntity[EheimDigitalClassicVario | EheimDigitalFilter], SwitchEntity
):
    """Represent an EHEIM Digital classicVARIO or filter switch entity."""

    _attr_translation_key = "filter_active"
    _attr_name = None

    def __init__(
        self,
        coordinator: EheimDigitalUpdateCoordinator,
        device: EheimDigitalClassicVario | EheimDigitalFilter,
    ) -> None:
        """Initialize an EHEIM Digital classicVARIO or filter switch entity."""
        super().__init__(coordinator, device)
        self._attr_unique_id = device.mac_address
        self._async_update_attrs()

    @override
    @exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.set_active(active=False)

    @override
    @exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._device.set_active(active=True)

    @override
    def _async_update_attrs(self) -> None:
        self._attr_is_on = self._device.is_active
