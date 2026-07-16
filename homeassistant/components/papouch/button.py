"""File contains default class for Papouch's buttons (UI)."""

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PapouchConfigEntry
from .entity import PapouchEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PapouchConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Entry for Home Assistant."""
    coordinator = entry.runtime_data
    device = coordinator.device

    entities = [
        PapouchCommandButton(
            coordinator=coordinator,
            entry=entry,
            name=btn_data["name"],
            id_suffix=btn_data["cmd"],
            cmd_type=btn_data["cmd"],
        )
        for btn_data in device.get_supported_buttons()
    ]

    async_add_entities(entities)


class PapouchCommandButton(PapouchEntity, ButtonEntity):
    """Default Command Button Class for Papouch's devices."""

    def __init__(
        self, coordinator, entry, name: str, cmd_type: str, id_suffix: str
    ) -> None:
        """Constructor of the button.

        Note that it needs the command type that
        will be later used to call that function in the proper device.

        ID suffix is not optional and should be unique.
        """

        super().__init__(coordinator, entry)
        self.cmd_type = cmd_type

        self._attr_unique_id = f"{entry.entry_id}_btn_{id_suffix}"
        self._attr_name = name

    async def async_press(self) -> None:
        """Home Assistant function for pressing the button.

        Note that this function uses dynamic lookup, make sure method in proper device
        and function that was provided to the ctor of the button is the same.
        This is done for the readability of the code.
        """

        command_method = getattr(self.coordinator.device, self.cmd_type)
        await command_method()

        await self.coordinator.async_request_refresh()
