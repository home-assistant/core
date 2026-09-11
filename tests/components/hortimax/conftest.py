"""Fixtures for the Ridder HortiMaX Pro (HortOS) tests."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from aiohortos import Device, Organisation, Readout, TokenPair
import pytest

from homeassistant.components.hortimax.const import DOMAIN
from homeassistant.const import CONF_API_KEY

from tests.common import MockConfigEntry, load_json_array_fixture

API_KEY = "test-api-key"
DEVICE = "HOR00000000.000"
DEVICE_LABEL = "Greenhouse Multima"
ORGANISATION_ID = "9006"


def load_readouts() -> list[Readout]:
    """Return the fixture readouts, parsed the way the library parses them."""
    return [
        readout
        for raw in load_json_array_fixture("readouts.json", DOMAIN)
        if (readout := Readout.from_api(raw)) is not None
    ]


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.hortimax.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Ridder HortiMaX Pro",
        data={CONF_API_KEY: API_KEY},
        unique_id=ORGANISATION_ID,
    )


@pytest.fixture
def mock_hortos_client() -> Generator[AsyncMock]:
    """Return a mocked HortOS client, shared by both of its import sites."""
    now = datetime(2026, 6, 12, 8, 0, tzinfo=UTC)
    with (
        patch(
            "homeassistant.components.hortimax.HortosClient", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.hortimax.config_flow.HortosClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.authenticate.return_value = TokenPair(
            token="token",
            expires_at=now + timedelta(minutes=15),
            refresh_token="refresh-token",
            refresh_expires_at=now + timedelta(days=7),
            organisation=Organisation(id=ORGANISATION_ID, name="Test organisation"),
        )
        client.get_device_names.return_value = [DEVICE]
        client.get_devices.return_value = [
            Device(name=DEVICE, label=DEVICE_LABEL, public_id="public-id")
        ]
        client.get_latest_readouts.return_value = load_readouts()
        yield client
