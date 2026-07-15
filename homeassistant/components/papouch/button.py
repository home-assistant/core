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

    # TODO: create a signpost for various devices for now its hard-coded for Quido
    # Place for creating a new button:
    # First and second parameter should be the same
    # third - name visible in HA
    # forth - function that will be looked up in APIClient
    # fifth - suffix for item id, should be unique and describes the button

    entities = [
        PapouchCommandButton(
            coordinator,
            entry,
            "Reset all counters",
            "reset_all_counters",
            "reset_all_counters",
        ),
        PapouchCommandButton(
            coordinator,
            entry,
            "Connect all coils",
            "connect_all_coils",
            "connect_all_coils",
        ),
        PapouchCommandButton(
            coordinator,
            entry,
            "Disconnect all coils",
            "disconnect_all_coils",
            "disconnect_all_coils",
        ),
    ]

    async_add_entities(entities)


class PapouchCommandButton(PapouchEntity, ButtonEntity):
    """Default Command Button Class for Papouch's devices."""

    def __init__(
        self, coordinator, entry, name: str, cmd_type: str, id_suffix: str
    ) -> None:
        """Constructor of the button.

        Note that it needs the command type that
        will be later used to call that function in the APIClient.

        ID suffix is not optional and should be unique.
        """

        super().__init__(coordinator, entry)
        self.cmd_type = cmd_type

        self._attr_unique_id = f"{entry.entry_id}_btn_{id_suffix}"
        self._attr_name = name

    async def async_press(self) -> None:
        """Home Assistant function for pressing the button.

        Note that this function uses dynamic lookup, make sure that function in
        APIClient.py and function that was provided to the ctor of the button is the same.
        This is done for readability of the
        """

        command_method = getattr(self.coordinator.device, self.cmd_type)
        await command_method()

        await self.coordinator.async_request_refresh()
