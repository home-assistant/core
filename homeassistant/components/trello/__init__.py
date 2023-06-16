"""The Trello integration."""
from __future__ import annotations

from typing import Any

from trello import Member, TrelloClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import LOGGER

PLATFORMS: list[str] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_entry))

    return True


async def async_update_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update a given config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class TrelloAdapter:
    """Adapter for Trello lib's client."""

    def __init__(self, client: TrelloClient) -> None:
        """Initialize with Trello lib client."""
        self.client = client

    @classmethod
    def from_creds(cls, api_key: str, api_token: str) -> TrelloAdapter:
        """Initialize with API Key and API Token."""
        return cls(TrelloClient(api_key=api_key, api_secret=api_token))

    def get_member(self) -> Member:
        """Get member information."""
        return self.client.get_member("me")

    def get_boards(self) -> dict[str, dict[str, str]]:
        """Get all user's boards."""
        return {
            board.id: {"id": board.id, "name": board.name}
            for board in self.client.list_boards(board_filter="open")
        }

    def get_board_lists(
        self, id_boards: dict[str, dict[str, str]], selected_board_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        """Fetch lists for selected boards.

        :param id_boards: All boards
        :param selected_board_ids: Board IDs the user has selected
        :return: Selected boards populated with the IDs of their lists
        """
        sub_query_params = "fields=name"
        urls = ",".join(
            f"/boards/{board_id}/lists?{sub_query_params}"
            for board_id in selected_board_ids
        )

        batch_response = (
            self.client.fetch_json("batch", query_params={"urls": urls}) if urls else []
        )
        user_selected_boards = {}
        for i, board_lists_response in enumerate(batch_response):
            board = dict(id_boards[selected_board_ids[i]])
            if _is_success(board_lists_response):
                board["lists"] = board_lists_response["200"]
            else:
                LOGGER.error(
                    "Unable to fetch lists for board named '%s' with ID '%s'. Response was: %s)",
                    board["name"],
                    board["id"],
                    board_lists_response,
                )
                continue

            user_selected_boards[board["id"]] = board

        return user_selected_boards


def _is_success(response: dict) -> bool:
    return "200" in response
