"""Common fixtures for the Solarman tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.solarman.const import CONF_SN, DOMAIN, MODEL_NAME_MAP
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL

from tests.common import MockConfigEntry, load_json_object_fixture

TEST_HOST = "192.168.1.100"
TEST_PORT = 8080
TEST_DEVICE_SN = "SN1234567890"
TEST_MODEL = "SP-2W-EU"
TEST_MAC = "AA:BB:CC:DD:EE:FF"


@pytest.fixture
def device_fixture(request: pytest.FixtureRequest) -> str | None:
    """Return the device fixtures for a specific device."""
    return getattr(request, "param", None)


@pytest.fixture
def mock_config_entry(device_fixture: str) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"{MODEL_NAME_MAP[device_fixture]} ({TEST_HOST})",
        data={
            CONF_HOST: TEST_HOST,
            CONF_SN: TEST_DEVICE_SN,
            CONF_MODEL: device_fixture,
            CONF_MAC: TEST_MAC,
        },
        unique_id=TEST_DEVICE_SN,
    )


@pytest.fixture
def mock_solarman(device_fixture: str) -> Generator[AsyncMock]:
    """Mock a solarman client."""
    with (
        patch(
            "homeassistant.components.solarman.coordinator.Solarman",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.solarman.config_flow.Solarman",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_config.return_value = load_json_object_fixture(
            f"{device_fixture}/config.json", DOMAIN
        )
        client.fetch_data.return_value = load_json_object_fixture(
            f"{device_fixture}/data.json", DOMAIN
        )
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.solarman.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
