"""Button platform for the Papouch integration."""

from typing import Any, override

import aiopapouch.exceptions as aiopapouch_exceptions

from homeassistant.components.button import ButtonEntity
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
    """Set up the button platform."""
    coordinator = entry.runtime_data
    device = coordinator.device

    entities = [
        PapouchCommandButton(coordinator, entry, btn_data)
        for btn_data in device.get_supported_buttons()
    ]

    async_add_entities(entities)


class PapouchCommandButton(PapouchEntity, ButtonEntity):
    """Representation of a generic Papouch button entity."""

    def __init__(
        self,
        coordinator: PapouchDataUpdateCoordinator,
        entry: PapouchConfigEntry,
        btn_data: dict[str, Any],
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, entry)

        mac = format_mac(coordinator.device.mac_address)

        self.cmd_type = btn_data["cmd"]

        self._attr_unique_id = f"{mac}_btn_{self.cmd_type}"

        if btn_data.get("use_custom_name", False):
            self._attr_name = btn_data["name"]
        else:
            self._attr_translation_key = btn_data["translation"]
            if "placeholder" in btn_data:
                self._attr_translation_placeholders = btn_data["placeholder"]

    @override
    async def async_press(self) -> None:
        """Execute the command."""

        try:
            await self.coordinator.device.execute_button_command(self.cmd_type)
            self.coordinator.async_set_updated_data(self.coordinator.data)

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
                    "cmd": self.cmd_type,
                    "name": self.coordinator.device.name,
                }
            ) from err
