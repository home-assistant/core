"""Common fixtures for the IOmeter tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from iometer import Reading, Status
import pytest

from homeassistant.components.iometer.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.iometer.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_iometer_client() -> Generator[AsyncMock]:
    """Mock a new IOmeter client."""
    with (
        patch(
            "homeassistant.components.iometer.IOmeterClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.iometer.config_flow.IOmeterClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.host = "10.0.0.2"
        client.get_current_reading.return_value = Reading.from_json(
            load_fixture("reading.json", DOMAIN)
        )
        client.get_current_status.return_value = Status.from_json(
            load_fixture("status.json", DOMAIN)
        )
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a IOmeter config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="IOmeter-1ISK0000000000",
        data={CONF_HOST: "10.0.0.2"},
        unique_id="658c2b34-2017-45f2-a12b-731235f8bb97",
        entry_id="01JQ6G5395176MAAWKAAPEZHV6",
    )
