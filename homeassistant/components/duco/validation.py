"""Validation helpers for supported Duco systems."""

from awesomeversion import (
    AwesomeVersion,
    AwesomeVersionStrategy,
    AwesomeVersionStrategyException,
)
from duco_connectivity import DucoClient
from duco_connectivity.exceptions import DucoResponseError
from duco_connectivity.models import BoardInfo

# Newer Connectivity boards expose /info with PublicApiVersion. We use that
# endpoint to distinguish supported Connectivity hardware from older
# Communication board V1 hardware.
_MIN_PUBLIC_API_VERSION = AwesomeVersion(
    "2.1", ensure_strategy=AwesomeVersionStrategy.SIMPLEVER
)


class UnsupportedBoardError(Exception):
    """Raised when the Duco system is not supported by this integration."""


def validate_board_support(board_info: BoardInfo) -> None:
    """Raise UnsupportedBoardError if the board does not meet support requirements."""
    version = board_info.public_api_version
    if version is None:
        raise UnsupportedBoardError("Board did not report a public API version")
    try:
        parsed_version = AwesomeVersion(
            version, ensure_strategy=AwesomeVersionStrategy.SIMPLEVER
        )
    except AwesomeVersionStrategyException as err:
        raise UnsupportedBoardError(
            f"Board reported malformed public API version: {version}"
        ) from err
    if parsed_version < _MIN_PUBLIC_API_VERSION:
        raise UnsupportedBoardError(
            "Board public API version "
            f"{version} is below the supported minimum {_MIN_PUBLIC_API_VERSION}"
        )


async def async_get_supported_board_info(client: DucoClient) -> BoardInfo:
    """Fetch and validate board info for a supported Duco system."""
    try:
        board_info = await client.async_get_board_info()
    except DucoResponseError as err:
        if err.status == 404:
            # Duco indicated that Communication board V1 does not implement
            # /info, so a 404 is enough to treat the device as unsupported.
            raise UnsupportedBoardError(
                "Board does not expose the /info endpoint"
            ) from err
        raise

    validate_board_support(board_info)
    return board_info
