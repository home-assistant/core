"""Common fixtures for the ecosmart tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aioecosmart import Forecast, Identity, Spot
import pytest

from homeassistant.components.ecosmart.const import DOMAIN
from homeassistant.const import CONF_API_KEY

from tests.common import MockConfigEntry, load_json_object_fixture

TEST_API_KEY = "ecos_live_abcd1234efgh5678"
TEST_ACCOUNT_REF = "ACC-000000"
TEST_ICP = "0000123456AB123"
TEST_POC = "BOB1101"


def load_identity(filename: str = "me.json") -> Identity:
    """Build an Identity from a recorded, redacted fixture."""
    return Identity.from_dict(load_json_object_fixture(filename, DOMAIN))


def load_spot(filename: str = "spot.json") -> Spot:
    """Build a Spot from a recorded, redacted fixture."""
    return Spot.from_dict(load_json_object_fixture(filename, DOMAIN))


def load_forecast(filename: str = "forecast.json") -> Forecast:
    """Build a Forecast from a recorded, redacted fixture."""
    return Forecast.from_dict(load_json_object_fixture(filename, DOMAIN))


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ecosmart.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_ecosmart_client() -> Generator[AsyncMock]:
    """Mock the ecosmart API client with fixture-built models."""
    with (
        patch(
            "homeassistant.components.ecosmart.EcosmartClient", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.ecosmart.config_flow.EcosmartClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.me.return_value = load_identity()
        client.spot.return_value = load_spot()
        client.forecast.return_value = load_forecast()
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock ecosmart config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="redacted",
        unique_id=TEST_ACCOUNT_REF,
        data={CONF_API_KEY: TEST_API_KEY},
        entry_id="01K3QW9YH2T4V6X8Z0B2D4F6H8",
    )
