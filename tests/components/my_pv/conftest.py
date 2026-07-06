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
def mock_my_pv_client() -> Generator[AsyncMock]:
    """Mock the my-PV client across the integration."""
    with (
        patch(
            "my_pv.MyPVLocalDevice",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.my_pv.config_flow.MyPVLocalDevice",
            new=mock_client,
        ),
        patch(
            "homeassistant.components.my_pv.MyPVLocalDevice",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.serial_number = ELWA2_SERIAL_NUMBER
        client.model = "AC ELWA 2"

        yield client
