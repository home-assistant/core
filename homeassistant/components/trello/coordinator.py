"""Data update coordinator for the Trello integration."""
from __future__ import annotations

from datetime import timedelta

from trello import TrelloClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import LOGGER


class TrelloDataUpdateCoordinator(DataUpdateCoordinator[dict[str, int]]):
    """Data update coordinator for the Trello integration."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, trello_client: TrelloClient, board_ids: list[str]
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name="trello",
            update_interval=timedelta(seconds=60),
        )
        self.client = trello_client
        self.board_ids = board_ids

    def _update(self) -> dict[str, int]:
        """Fetch data for all sensors using batch API endpoint."""
        sub_query_params = "fields=name&cards=open&card_fields=none"
        urls = ",".join(
            f"/boards/{board_id}/lists?{sub_query_params}"
            for board_id in self.board_ids
        )

        LOGGER.debug("Fetching boards lists: %s", urls)
        batch_response = self.client.fetch_json("batch", query_params={"urls": urls})

        return _get_lists_card_counts(batch_response, self.board_ids)

    async def _async_update_data(self) -> dict[str, int]:
        """Send request to the executor."""
        return await self.hass.async_add_executor_job(self._update)


def _get_lists_card_counts(
    batch_response: list[dict], board_ids: list[str]
) -> dict[str, int]:
    list_card_counts = {}
    for i, board_lists_response in enumerate(batch_response):
        if _is_success(board_lists_response):
            lists = board_lists_response["200"]
            for list_ in lists:
                list_card_counts[list_["id"]] = len(list_["cards"])
        else:
            LOGGER.error(
                "Unable to fetch lists for board with ID '%s'. Response was: %s)",
                board_ids[i],
                board_lists_response,
            )
            continue

    return list_card_counts


def _is_success(response: dict) -> bool:
    return "200" in response
