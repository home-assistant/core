"""Fixtures for the MAWAQIT integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from mawaqit.types import Account, Mosque, PrayerTimes
import pytest

from homeassistant.components.mawaqit.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_UUID

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)

MOSQUE_UUID = "05b4d393-fb76-4d9b-b2a4-f98ab4c4b64f"
TOKEN = "test-api-token"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a MAWAQIT config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="GRANDE MOSQUÉE DE PARIS",
        data={CONF_API_KEY: TOKEN, CONF_UUID: MOSQUE_UUID},
    )


@pytest.fixture
def prayer_times() -> PrayerTimes:
    """Return the prayer times of the mosque."""
    return PrayerTimes.model_validate(
        load_json_object_fixture("prayer_times.json", DOMAIN)
    )


@pytest.fixture
def mock_mawaqit_client(prayer_times: PrayerTimes) -> Generator[MagicMock]:
    """Mock the MAWAQIT client."""
    client = MagicMock()
    client.auth.login = AsyncMock(
        return_value=Account(
            id=1, api_access_token=TOKEN, api_quota=None, api_call_number=0
        )
    )
    client.mosques.search = AsyncMock(
        return_value=[
            Mosque.model_validate(mosque)
            for mosque in load_json_array_fixture("search.json", DOMAIN)
        ]
    )
    client.mosques.prayer_times = AsyncMock(return_value=prayer_times)
    with (
        patch(
            "homeassistant.components.mawaqit.AsyncMawaqitClient", return_value=client
        ),
        patch(
            "homeassistant.components.mawaqit.config_flow.AsyncMawaqitClient",
            return_value=client,
        ),
    ):
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.mawaqit.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
