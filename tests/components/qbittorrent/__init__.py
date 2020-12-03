"""Tests for the Qbittorrent integration."""

from requests.exceptions import RequestException

from tests.async_mock import AsyncMock, MagicMock


def _create_mocked_client(raise_exception=False):
    mocked_client = MagicMock()
    type(mocked_client).get_data = AsyncMock(
        side_effect=RequestException("") if raise_exception else None
    )
    return mocked_client
