"""EHEIM Digital switches."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from eheimdigital.classic_vario import EheimDigitalClassicVario
from eheimdigital.device import EheimDigitalDevice
from eheimdigital.filter import EheimDigitalFilter
from eheimdigital.reeflex import EheimDigitalReeflexUV
from eheimdigital.types import MsgTitle

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EheimDigitalConfigEntry, EheimDigitalDeviceUpdateCoordinator
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
        key="is_active",
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
    """Set up callbacks for the coordinator to add switches as devices are found."""
    coordinator = entry.runtime_data

    def async_setup_device_entities(
        device_coordinator: EheimDigitalDeviceUpdateCoordinator[Any],
    ) -> None:
        """Set up the switch entities for one or multiple devices."""
        entities: list[SwitchEntity] = []
        if (
            isinstance(device_coordinator.data, EheimDigitalFilter)
            and device_coordinator.msg_title == MsgTitle.FILTER_DATA
        ) or (
            isinstance(device_coordinator.data, EheimDigitalClassicVario)
            and device_coordinator.msg_title == MsgTitle.CLASSIC_VARIO_DATA
        ):
            entities.append(EheimDigitalFilterSwitch(device_coordinator))
        if isinstance(device_coordinator.data, EheimDigitalReeflexUV):
            entities.extend(
                EheimDigitalSwitch[EheimDigitalReeflexUV](
                    device_coordinator, description
                )
                for description in REEFLEX_DESCRIPTIONS
                if description.key
                in device_coordinator.data.packet_mapping[device_coordinator.msg_title]
            )

        async_add_entities(entities)

    coordinator.add_platform_callback(async_setup_device_entities)


class EheimDigitalSwitch[_DeviceT: EheimDigitalDevice](
    EheimDigitalEntity[_DeviceT], SwitchEntity
):
    """Represent a EHEIM Digital switch entity."""

    entity_description: EheimDigitalSwitchDescription[_DeviceT]

    def __init__(
        self,
        coordinator: EheimDigitalDeviceUpdateCoordinator[_DeviceT],
        description: EheimDigitalSwitchDescription[_DeviceT],
    ) -> None:
        """Initialize an EHEIM Digital switch entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_address}_{description.key}"

    @exception_handler
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        return await self.entity_description.set_fn(self._device, True)

    @exception_handler
    @override
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
        coordinator: EheimDigitalDeviceUpdateCoordinator[
            EheimDigitalClassicVario | EheimDigitalFilter
        ],
    ) -> None:
        """Initialize an EHEIM Digital classicVARIO or filter switch entity."""
        super().__init__(coordinator)
        self._attr_unique_id = self._device_address
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
