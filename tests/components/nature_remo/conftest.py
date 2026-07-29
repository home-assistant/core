"""Common fixtures for Nature Remo integration tests."""

from __future__ import annotations

from collections.abc import Generator
from datetime import timedelta
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from aionatureremo import Appliance, Device, NatureRemoClient, RateLimit, User
import pytest

from homeassistant.components.nature_remo.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed

FIXTURES = Path(__file__).parent / "fixtures"


def load_json_fixture(name: str) -> list[dict[str, object]]:
    """Load a JSON fixture file."""
    return json.loads((FIXTURES / name).read_text())


async def async_poll(hass: HomeAssistant, times: int = 1) -> None:
    """Run `times` real coordinator polls, settling the event loop after each."""
    for _ in range(times):
        async_fire_time_changed(
            hass, dt_util.utcnow() + UPDATE_INTERVAL + timedelta(seconds=1)
        )
        await hass.async_block_till_done()


@pytest.fixture
def devices() -> list[Device]:
    """Devices parsed from the fixture payload."""
    return [Device.from_dict(item) for item in load_json_fixture("devices.json")]


@pytest.fixture
def appliances() -> list[Appliance]:
    """Appliances parsed from the fixture payload."""
    return [Appliance.from_dict(item) for item in load_json_fixture("appliances.json")]


@pytest.fixture
def mock_client(
    devices: list[Device], appliances: list[Appliance]
) -> Generator[AsyncMock]:
    """Build a mocked NatureRemoClient preloaded with fixture data.

    Specced against the real client so a test stubbing a method the library
    does not have fails loudly instead of asserting against a mock that can
    never be called. ``rate_limit`` is an instance attribute (the spec is the
    class), so it is assigned rather than stubbed — ``spec`` restricts reads,
    not writes.
    """
    client = AsyncMock(spec=NatureRemoClient)
    client.get_user.return_value = User(id="user-1", nickname="Alice")
    client.get_devices.return_value = devices
    client.get_appliances.return_value = appliances
    client.rate_limit = RateLimit(limit=30, remaining=25, reset=1752825600)
    with (
        patch(
            "homeassistant.components.nature_remo.NatureRemoClient", return_value=client
        ),
        patch(
            "homeassistant.components.nature_remo.config_flow.NatureRemoClient",
            return_value=client,
        ),
    ):
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Build a config entry for the fixture account."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Alice",
        data={CONF_API_TOKEN: "test-token"},
        unique_id="user-1",
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> MockConfigEntry:
    """Set up the integration with the mocked client."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
