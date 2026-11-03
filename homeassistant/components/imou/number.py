"""Support for Imou number entities."""

from typing import override

from pyimouapi.const import PARAM_REF, PARAM_STATE
from pyimouapi.ha_device import ImouHaDevice

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    OVERCHARGE_HIGH_REF,
    OVERCHARGE_MAX_WATTS_DEFAULT,
    OVERCHARGE_MAX_WATTS_HIGH,
    OVERCHARGE_MIN_WATTS,
    PARAM_OVERCHARGE_SWITCH,
    imou_device_identifier,
)
from .coordinator import ImouConfigEntry, ImouDataUpdateCoordinator
from .entity import ImouEntity
from .helpers import async_wrap_imou_command

PARALLEL_UPDATES = 0

OVERCHARGE_NUMBER = NumberEntityDescription(
    key=PARAM_OVERCHARGE_SWITCH,
    translation_key=PARAM_OVERCHARGE_SWITCH,
    entity_category=EntityCategory.CONFIG,
    device_class=NumberDeviceClass.POWER,
    native_min_value=OVERCHARGE_MIN_WATTS,
    native_step=1,
    native_unit_of_measurement=UnitOfPower.WATT,
    mode=NumberMode.BOX,
)


def _iter_overcharge_numbers(
    coordinator: ImouDataUpdateCoordinator,
) -> list[tuple[NumberEntityDescription, ImouHaDevice]]:
    """Return max-power numbers for plugs that expose the limit."""
    return [
        (OVERCHARGE_NUMBER, device)
        for device in coordinator.devices
        if PARAM_OVERCHARGE_SWITCH in device.texts
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImouConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Imou number entities."""
    coordinator = entry.runtime_data

    def _add_numbers(new_devices: list[ImouHaDevice]) -> None:
        device_keys = {imou_device_identifier(device) for device in new_devices}
        async_add_entities(
            ImouOverchargeNumber(coordinator, description, device)
            for description, device in _iter_overcharge_numbers(coordinator)
            if imou_device_identifier(device) in device_keys
        )

    entry.async_on_unload(coordinator.register_new_device_callback(_add_numbers))
    _add_numbers(coordinator.devices)


class ImouOverchargeNumber(ImouEntity, NumberEntity):
    """Plug max power in watts."""

    entity_description: NumberEntityDescription

    @property
    @override
    def native_max_value(self) -> float:
        """Higher-capacity plugs accept a larger watt limit."""
        ref = self.device.texts[PARAM_OVERCHARGE_SWITCH].get(PARAM_REF)
        if ref == OVERCHARGE_HIGH_REF:
            return float(OVERCHARGE_MAX_WATTS_HIGH)
        return float(OVERCHARGE_MAX_WATTS_DEFAULT)

    @property
    @override
    def native_value(self) -> float | None:
        """Return the configured watt limit."""
        raw = self.device.texts[PARAM_OVERCHARGE_SWITCH][PARAM_STATE]
        try:
            return float(int(raw))
        except TypeError, ValueError:
            return None

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Write the watt limit to the device."""
        await self._async_write_text(str(int(value)))
        self.async_write_ha_state()

    @async_wrap_imou_command("set_text_value_failed")
    async def _async_write_text(self, text_value: str) -> None:
        await self.coordinator.device_manager.async_set_text_value(
            self.device,
            PARAM_OVERCHARGE_SWITCH,
            text_value,
        )
