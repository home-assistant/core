"""Common fixtures for the IOmeter tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from iometer import Reading, Status
import pytest

from homeassistant.components.iometer.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[MagicMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.iometer.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_http_client() -> Generator[MagicMock]:
    """Mock IOmeter HTTP client for config flow."""
    with patch(
        "homeassistant.components.iometer.config_flow.IOmeterClient"
    ) as mock_http_class:
        http_client = mock_http_class.return_value
        http_client.get_current_status = AsyncMock(
            return_value=Status.from_json(load_fixture("status.json", DOMAIN))
        )
        yield http_client


@pytest.fixture
def mock_iometer_client(mock_http_client: MagicMock) -> Generator[MagicMock]:
    """Mock IOmeter SSE client for the coordinator."""

    def subscribe_readings(on_reading, _on_error=None):
        on_reading(Reading.from_json(load_fixture("reading.json", DOMAIN)))
        return lambda: None

    def subscribe_status(on_status, _on_error=None):
        on_status(Status.from_json(load_fixture("status.json", DOMAIN)))
        return lambda: None

    with patch("homeassistant.components.iometer.IOmeterSSEClient") as mock_sse_class:
        sse_client = mock_sse_class.return_value
        sse_client.subscribe_readings.side_effect = subscribe_readings
        sse_client.subscribe_status.side_effect = subscribe_status
        yield sse_client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock an IOmeter config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="IOmeter-1ISK0000000000",
        data={CONF_HOST: "10.0.0.2"},
        unique_id="658c2b34-2017-45f2-a12b-731235f8bb97",
        entry_id="01JQ6G5395176MAAWKAAPEZHV6",
    )
