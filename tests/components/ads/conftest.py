"""Common fixtures for the ADS tests."""

from collections.abc import Generator
from typing import NamedTuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.ads import hub as ads_hub
from homeassistant.components.ads.const import DOMAIN
from homeassistant.const import CONF_DEVICE, CONF_IP_ADDRESS, CONF_PORT

from .const import AMS_NET_ID, AUTO_NET_ID

from tests.common import MockConfigEntry


class MockPyadsLocalNetId(NamedTuple):
    """Mocks for the pyads local AMS NetID functions."""

    open_port: MagicMock
    get_local_address: MagicMock
    set_local_address: MagicMock
    close_port: MagicMock


@pytest.fixture(autouse=True)
def _reset_local_net_id_cache() -> None:
    """Ensure the cached original AMS NetID does not leak between tests."""
    ads_hub._reset_local_net_id_cache()


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ads.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_pyads_connection() -> Generator[MagicMock]:
    """Mock the pyads Connection class."""
    with patch("pyads.Connection", autospec=True) as mock_connection:
        yield mock_connection


@pytest.fixture
def mock_pyads_local_net_id() -> Generator[MockPyadsLocalNetId]:
    """Mock the pyads local AMS NetID functions."""
    with (
        patch("pyads.open_port", autospec=True) as mock_open_port,
        patch("pyads.get_local_address", autospec=True) as mock_get_local_address,
        patch("pyads.set_local_address", autospec=True) as mock_set_local_address,
        patch("pyads.close_port", autospec=True) as mock_close_port,
    ):
        mock_get_local_address.return_value.netid = AUTO_NET_ID
        yield MockPyadsLocalNetId(
            mock_open_port,
            mock_get_local_address,
            mock_set_local_address,
            mock_close_port,
        )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=AMS_NET_ID,
        data={
            CONF_DEVICE: AMS_NET_ID,
            CONF_IP_ADDRESS: "192.168.1.10",
            CONF_PORT: 851,
        },
    )
