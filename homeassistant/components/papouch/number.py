"""Number platform for the Papouch integration."""

from typing import Any, override

import aiopapouch.exceptions as aiopapouch_exceptions

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PapouchConfigEntry
from .coordinator import PapouchDataUpdateCoordinator
from .entity import PapouchEntity
from .exceptions import PapouchAuthError, PapouchCommandError, PapouchConnectionError

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PapouchConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the number platform."""
    coordinator = entry.runtime_data
    device = coordinator.device

    entities = [
        PapouchNumber(coordinator, entry, number_data)
        for number_data in device.get_supported_numbers()
    ]
    async_add_entities(entities)


class PapouchNumber(PapouchEntity, NumberEntity):
    """Representation of a generic Papouch number entity."""

    def __init__(
        self,
        coordinator: PapouchDataUpdateCoordinator,
        entry: PapouchConfigEntry,
        number_data: dict[str, Any],
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, entry)

        mac = format_mac(coordinator.device.mac_address)

        self.item_id = number_data["item_id"]
        self.category = number_data["category"]

        self._attr_unique_id = f"{mac}_{self.category}_{self.item_id}"

        if number_data.get("use_custom_name", False):
            self._attr_name = number_data["name"]
        else:
            self._attr_translation_key = number_data["translation"]
            if "placeholder" in number_data:
                self._attr_translation_placeholders = number_data["placeholder"]

        self._attr_native_min_value = number_data.get("min_value", 0)
        self._attr_native_max_value = number_data.get("max_value", 100)
        self._attr_native_step = number_data.get("step", 1)

        self._attr_mode = NumberMode(number_data.get("mode", "box"))

        if "icon" in number_data:
            self._attr_icon = number_data["icon"]

        self._current_value: float = 1

    @override
    @property
    def native_value(self) -> float:
        """Return the local value, NOT the real hardware counter."""
        return self._current_value

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Send the command and update the UI."""

        try:
            await self.coordinator.device.set_number_value(
                self.category, self.item_id, value
            )
        except aiopapouch_exceptions.DeviceAuthError as err:
            raise PapouchAuthError(
                translation_placeholders={"name": self.coordinator.device.name}
            ) from err
        except aiopapouch_exceptions.DeviceConnectionError as err:
            raise PapouchConnectionError(
                translation_placeholders={
                    "name": self.coordinator.device.name,
                    "location": self.coordinator.device.location,
                }
            ) from err
        except aiopapouch_exceptions.DeviceError as err:
            raise PapouchCommandError(
                translation_placeholders={
                    "cmd": f"set_{self.category}",
                    "name": self.coordinator.device.name,
                }
            ) from err

        self._current_value = value
        self.async_write_ha_state()

        await self.coordinator.async_request_refresh()
