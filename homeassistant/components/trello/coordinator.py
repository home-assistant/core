"""Data update coordinator for the Trello integration."""

from __future__ import annotations

from datetime import timedelta

from trello import BatchResponse, Board as TrelloBoard, List as TrelloList, TrelloClient
from trello.batch.board import Board as BatchBoard

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import LOGGER
from .models import Board, List


class TrelloDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Board]]):
    """Data update coordinator for the Trello integration."""

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
        """Fetch data for all sensors as a batch."""
        batch_requests = []
        for board_id in self.board_ids:
            batch_requests.append(BatchBoard.GetBoard(board_id, ["name"]))
            batch_requests.append(
                BatchBoard.GetLists(board_id, ["name"], "open", ["idCard"])
            )
        LOGGER.debug("Fetching boards lists")
        batch_responses = self.client.fetch_batch(batch_requests)

        return _get_boards(batch_responses, self.board_ids)

    async def _async_update_data(self) -> dict[str, Board]:
        """Send request to the executor."""
        return await self.hass.async_add_executor_job(self._update)


def _get_boards(
    batch_response: list[BatchResponse], board_ids: list[str]
) -> dict[str, Board]:
    board_id_boards: dict[str, Board] = {}
    for i, batch_response_pair in enumerate(
        zip(batch_response[::2], batch_response[1::2], strict=False)
    ):
        board_response = batch_response_pair[0]
        list_response = batch_response_pair[1]
        if board_response.success and list_response.success:
            board = board_response.payload
            lists = list_response.payload
            board_id_boards[board.id] = _get_board(board, lists)
        else:
            LOGGER.error(
                "Unable to fetch lists for board with ID '%s'. Response was: %s)",
                board_ids[i],
                board_response.payload.message,
            )
            board_id_boards[board_ids[i]] = Board(board_ids[i], "", {})
            continue

    return board_id_boards


def _get_board(board: TrelloBoard, lists: list[TrelloList]) -> Board:
    return Board(
        board.id,
        board.name,
        {list_.id: List(list_.id, list_.name, len(list_.cards)) for list_ in lists},
    )
