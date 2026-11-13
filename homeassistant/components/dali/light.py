"""Support for Tridonic DALI lights."""

from typing import Any, override

from dali.address import GearShort
from dali.exceptions import DALISequenceError, ResponseError, TransmissionError
from dali.gear.general import DAPC

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_TYPE_LED, DOMAIN
from .coordinator import (
    DaliConfigEntry,
    DaliCoordinator,
    DaliGearData,
    _brightness_to_dali_level,
    _dali_level_to_brightness,
)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DaliConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the DALI light platform."""
    coordinator = entry.runtime_data
    known_addresses: set[int] = set()

    def async_add_new_entities() -> None:
        new_addresses = set(coordinator.data) - known_addresses
        known_addresses.update(new_addresses)
        async_add_entities(
            DaliLight(
                coordinator, entry.entry_id, entry.title, address, known_addresses
            )
            for address in new_addresses
            if _is_light(coordinator.data[address])
        )

    async_add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(async_add_new_entities))


def _is_light(gear: DaliGearData) -> bool:
    """Return whether a gear should be exposed as a light."""
    return DEVICE_TYPE_LED in gear.device_types


class DaliLight(CoordinatorEntity[DaliCoordinator], LightEntity):
    """Representation of a DALI light."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(
        self,
        coordinator: DaliCoordinator,
        entry_id: str,
        title: str,
        address: int,
        known_addresses: set[int],
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        self._address = address
        self._known_addresses = known_addresses
        self._attr_unique_id = f"{entry_id}_{address}"
        self._attr_device_info = coordinator.device_info(entry_id, title, address)

    @override
    async def async_removed_from_registry(self) -> None:
        """Stop tracking the address so the gear can be rediscovered."""
        self._known_addresses.discard(self._address)

    @property
    @override
    def available(self) -> bool:
        """Return whether the DALI gear is responding."""
        return super().available and self._address in self.coordinator.data

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the DALI gear is on."""
        level = self.coordinator.data[self._address].level
        return None if level is None else bool(level)

    @property
    @override
    def brightness(self) -> int | None:
        """Return the current DALI arc power level."""
        return self.coordinator.data[self._address].level

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        try:
            gear_data = self.coordinator.data[self._address]
            # Turning on without a brightness keeps the current level rather than
            # jumping an already-dimmed light to full output.
            default = gear_data.level or 255
            brightness = max(1, min(kwargs.get("brightness", default), 255))
            level = _brightness_to_dali_level(
                brightness, gear_data.linear_dimming, gear_data.min_level
            )
            if gear_data.max_level is not None:
                level = min(level, gear_data.max_level)
            await self.coordinator.driver.send(DAPC(GearShort(self._address), level))
            optimistic_level = _dali_level_to_brightness(
                level, gear_data.linear_dimming
            )
            await self.coordinator.async_update_gear(self._address, optimistic_level)
        except (
            TransmissionError,
            OSError,
            TimeoutError,
            DALISequenceError,
            ResponseError,
        ) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from err

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        try:
            await self.coordinator.driver.send(DAPC(GearShort(self._address), 0))
            await self.coordinator.async_update_gear(self._address, 0)
        except (
            TransmissionError,
            OSError,
            TimeoutError,
            DALISequenceError,
            ResponseError,
        ) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
            ) from err
