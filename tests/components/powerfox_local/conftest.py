"""Common fixtures for the Powerfox Local tests."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from powerfox import LocalResponse
import pytest

from homeassistant.components.powerfox_local.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_HOST

from . import MOCK_API_KEY, MOCK_DEVICE_ID, MOCK_HOST

from tests.common import MockConfigEntry


def _local_response() -> LocalResponse:
    """Return a mocked local response."""
    return LocalResponse(
        timestamp=datetime(2024, 11, 26, 10, 48, 51, tzinfo=UTC),
        power=111,
        energy_usage=1111111,
        energy_return=111111,
        energy_usage_high_tariff=111111,
        energy_usage_low_tariff=111111,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.powerfox_local.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_powerfox_local_client() -> Generator[AsyncMock]:
    """Mock a PowerfoxLocal client."""
    with (
        patch(
            "homeassistant.components.powerfox_local.coordinator.PowerfoxLocal",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.powerfox_local.config_flow.PowerfoxLocal",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.value.return_value = _local_response()
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a Powerfox Local config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Poweropti ({MOCK_DEVICE_ID[-5:]})",
        unique_id=MOCK_DEVICE_ID,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_API_KEY: MOCK_API_KEY,
        },
    )
