"""Data update coordinator for the Trello integration."""
from __future__ import annotations

from datetime import timedelta

from trello import TrelloClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import LOGGER, Board, List


class TrelloDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Board]]):
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

    def _update(self) -> dict[str, Board]:
        """Fetch data for all sensors using batch API endpoint."""
        board_lists_query_params = "fields=name"
        list_cards_query_params = "fields=name&cards=open&card_fields=idCard"
        urls = ",".join(
            f"/boards/{board_id}?{board_lists_query_params},/boards/{board_id}/lists?{list_cards_query_params}"
            for board_id in self.board_ids
        )

        LOGGER.debug("Fetching boards lists: %s", urls)
        batch_response = self.client.fetch_json("batch", query_params={"urls": urls})

        return _get_boards(batch_response, self.board_ids)

    async def _async_update_data(self) -> dict[str, Board]:
        """Send request to the executor."""
        return await self.hass.async_add_executor_job(self._update)


def _get_boards(batch_response: list[dict], board_ids: list[str]) -> dict[str, Board]:
    board_id_boards: dict[str, Board] = {}
    for i, batch_response_pair in enumerate(
        zip(batch_response[::2], batch_response[1::2])
    ):
        board_response = batch_response_pair[0]
        list_response = batch_response_pair[1]
        if _is_success(board_response) and _is_success(list_response):
            board = board_response["200"]
            lists = list_response["200"]
            board_id_boards[board["id"]] = _get_board(board, lists)
        else:
            LOGGER.error(
                "Unable to fetch lists for board with ID '%s'. Response was: %s)",
                board_ids[i],
                board_response,
            )
            board_id_boards[board_ids[i]] = Board(board_ids[i], "", {})
            continue

    return board_id_boards


def _get_board(board: dict, lists: dict) -> Board:
    return Board(
        board["id"],
        board["name"],
        {
            list_["id"]: List(list_["id"], list_["name"], len(list_["cards"]))
            for list_ in lists
        },
    )


def _is_success(response: dict) -> bool:
    return "200" in response
