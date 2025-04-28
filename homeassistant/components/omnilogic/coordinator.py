"""Coordinator for the Omnilogic Integration."""

from datetime import timedelta
import logging
from typing import Any

from omnilogic import OmniLogic, OmniLogicException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ALL_ITEM_KINDS

_LOGGER = logging.getLogger(__name__)


class OmniLogicUpdateCoordinator(DataUpdateCoordinator[dict[tuple, dict[str, Any]]]):
    """Class to manage fetching update data from single endpoint."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api: OmniLogic,
        name: str,
        config_entry: ConfigEntry,
        polling_interval: int,
    ) -> None:
        """Initialize the global Omnilogic data updater."""
        self.api = api

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=name,
            update_interval=timedelta(seconds=polling_interval),
        )

    async def _async_update_data(self):
        """Fetch data from OmniLogic."""
        try:
            data = await self.api.get_telemetry_data()

        except OmniLogicException as error:
            raise UpdateFailed(f"Error updating from OmniLogic: {error}") from error

        parsed_data = {}

        def get_item_data(item, item_kind, current_id, data):
            """Get data per kind of Omnilogic API item."""
            if isinstance(item, list):
                for single_item in item:
                    data = get_item_data(single_item, item_kind, current_id, data)

            if "systemId" in item:
                system_id = item["systemId"]
                current_id = (*current_id, item_kind, system_id)
                data[current_id] = item

            for kind in ALL_ITEM_KINDS:
                if kind in item:
                    data = get_item_data(item[kind], kind, current_id, data)

            return data

        return get_item_data(data, "Backyard", (), parsed_data)
