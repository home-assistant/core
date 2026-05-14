"""Validation helpers for supported Duco systems."""

from duco_connectivity import DucoClient
from duco_connectivity.exceptions import DucoResponseError
from duco_connectivity.models import BoardInfo

_SUPPORTED_BOX_NAMES: frozenset[str] = frozenset({"ENERGY", "FOCUS", "SILENT_CONNECT"})
_MIN_PUBLIC_API_VERSION: tuple[int, ...] = (2, 1)


class UnsupportedBoardError(Exception):
    """Raised when the Duco system is not supported by this integration."""


def validate_board_support(board_info: BoardInfo) -> None:
    """Raise UnsupportedBoardError if the board does not meet support requirements."""
    if board_info.box_name not in _SUPPORTED_BOX_NAMES:
        raise UnsupportedBoardError
    if board_info.public_api_version is None:
        raise UnsupportedBoardError
    version_tuple = tuple(
        int(part) for part in board_info.public_api_version.split(".")
    )
    if version_tuple < _MIN_PUBLIC_API_VERSION:
        raise UnsupportedBoardError


async def async_get_supported_board_info(client: DucoClient) -> BoardInfo:
    """Fetch and validate board info for a supported Duco system."""
    try:
        board_info = await client.async_get_board_info()
    except DucoResponseError as err:
        if err.status == 404:
            raise UnsupportedBoardError from err
        raise

    validate_board_support(board_info)
    return board_info
