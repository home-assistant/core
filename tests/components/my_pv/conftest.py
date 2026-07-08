"""Common fixtures for the my-PV tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.my_pv.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD

from . import ELWA2_SERIAL_NUMBER

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the my-PV mocked config entry for local devices."""
    return MockConfigEntry(
        title="my-PV AC ELWA 2 0000000000",
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PASSWORD: "test-password",
        },
        unique_id=ELWA2_SERIAL_NUMBER,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent running the real integration setup during tests."""
    with patch(
        "homeassistant.components.my_pv.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_my_pv_connection() -> Generator[AsyncMock]:
    """Mock the my-PV connection across the integration."""
    with (
        patch(
            "my_pv.connection.MyPVConnection",
            autospec=True,
        ) as mock_connection,
        patch("my_pv.MyPVHTTPConnection", new=mock_connection),
        patch("my_pv.MyPVHTTPSConnection", new=mock_connection),
    ):
        connection = mock_connection.return_value
        connection.mypv_dev = {
            "device": "AC ELWA 2",
            "number": 1,
            "sn": ELWA2_SERIAL_NUMBER,
            "fwversion": "e0002200",
        }
        connection.fetch_setup = AsyncMock(
            return_value={
                "device": "AC ELWA 2",
                "fwversion": "e0002200",
                "fwvers_bl": 101,
                "psversion": "ep108",
                "hwvers": "v1.5A",
                "serialno": ELWA2_SERIAL_NUMBER,
                "macadr": "98-6d-35-c0-00-00",
                "devmode": 1,
                "ww1target": 621,
            }
        )
        connection.fetch_data = AsyncMock(return_value={"temp1": 543})
        connection.set_setup_value = AsyncMock(return_value=True)
        connection.send_command = AsyncMock(return_value=True)

        yield connection
