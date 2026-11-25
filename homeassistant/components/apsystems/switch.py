"""The power switch which can be toggled via the APsystems local API integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from aiohttp.client_exceptions import ClientConnectionError
from APsystemsEZ1 import InverterReturnedError

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import (
    ApSystemsConfigEntry,
    ApSystemsData,
    Lake6Coordinator,
    Lake6Data,
    Lake6RuntimeData,
)
from .entity import ApSystemsEntity, Lake6Entity
from .lake6.const import LAKE6_SWITCH_ENTITY_TO_FIELD


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ApSystemsConfigEntry,
    add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    if isinstance(config_entry.runtime_data, Lake6RuntimeData):
        coordinator = config_entry.runtime_data.coordinator
        add_entities(
            Lake6SwitchEntity(coordinator, description)
            for description in LAKE6_SWITCHES
        )
        return

    add_entities([ApSystemsInverterSwitch(config_entry.runtime_data)], True)


class ApSystemsInverterSwitch(ApSystemsEntity, SwitchEntity):
    """The switch class for APSystems switches."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_translation_key = "inverter_status"

    def __init__(self, data: ApSystemsData) -> None:
        """Initialize the switch."""
        super().__init__(data)
        self._api = data.coordinator.api
        self._attr_unique_id = f"{data.device_id}_inverter_status"
        if data.coordinator.battery_system:
            self._attr_available = False

    async def async_update(self) -> None:
        """Update switch status and availability."""
        try:
            status = await self._api.get_device_power_status()
        except TimeoutError, ClientConnectionError, InverterReturnedError:
            self._attr_available = False
        else:
            self._attr_available = True
            self._attr_is_on = status

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._api.set_device_power_status(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._api.set_device_power_status(False)


@dataclass(frozen=True, kw_only=True)
class Lake6SwitchEntityDescription(SwitchEntityDescription):
    """Describes a Lake_6 boolean flag on `/modes`."""

    value_fn: Callable[[Lake6Data], bool | None]


LAKE6_SWITCHES: tuple[Lake6SwitchEntityDescription, ...] = (
    # The entity key differs from the device field name (eco) and is mapped
    # back through LAKE6_SWITCH_ENTITY_TO_FIELD.
    Lake6SwitchEntityDescription(
        key="eco_mode",
        translation_key="eco_mode",
        value_fn=lambda d: d.modes.eco,
    ),
)


class Lake6SwitchEntity(Lake6Entity, SwitchEntity):
    """A writable boolean flag backed by one `/modes` field."""

    entity_description: Lake6SwitchEntityDescription

    def __init__(
        self,
        coordinator: Lake6Coordinator,
        entity_description: Lake6SwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{self.device_id}_{entity_description.key}"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the flag reported by `/modes`."""
        return self.entity_description.value_fn(self.coordinator.data)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the flag on."""
        await self._async_write("1")

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the flag off."""
        await self._async_write("0")

    async def _async_write(self, value: str) -> None:
        """Write one flag."""
        field = LAKE6_SWITCH_ENTITY_TO_FIELD[self.entity_description.key]
        await self.coordinator.async_set_modes(**{field: value})
