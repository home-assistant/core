"""Common fixtures for the Hydrawise tests."""

from collections.abc import Awaitable, Callable, Generator
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from pydrawise.schema import (
    Controller,
    ControllerHardware,
    ScheduledZoneRun,
    ScheduledZoneRuns,
    User,
    Zone,
)
import pytest

from homeassistant.components.hydrawise.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.hydrawise.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_pydrawise(
    user: User,
    controller: Controller,
    zones: list[Zone],
) -> Generator[AsyncMock, None, None]:
    """Mock LegacyHydrawiseAsync."""
    with patch(
        "pydrawise.legacy.LegacyHydrawiseAsync", autospec=True
    ) as mock_pydrawise:
        user.controllers = [controller]
        controller.zones = zones
        mock_pydrawise.return_value.get_user.return_value = user
        yield mock_pydrawise.return_value


@pytest.fixture
def user() -> User:
    """Hydrawise User fixture."""
    return User(customer_id=12345)


@pytest.fixture
def controller() -> Controller:
    """Hydrawise Controller fixture."""
    return Controller(
        id=52496,
        name="Home Controller",
        hardware=ControllerHardware(
            serial_number="0310b36090",
        ),
        last_contact_time=datetime.fromtimestamp(1693292420),
        online=True,
    )


@pytest.fixture
def zones() -> list[Zone]:
    """Hydrawise zone fixtures."""
    return [
        Zone(
            name="Zone One",
            number=1,
            id=5965394,
            scheduled_runs=ScheduledZoneRuns(
                summary="",
                current_run=None,
                next_run=ScheduledZoneRun(
                    start_time=dt_util.now() + timedelta(seconds=330597),
                    end_time=dt_util.now()
                    + timedelta(seconds=330597)
                    + timedelta(seconds=1800),
                    normal_duration=timedelta(seconds=1800),
                    duration=timedelta(seconds=1800),
                ),
            ),
        ),
        Zone(
            name="Zone Two",
            number=2,
            id=5965395,
            scheduled_runs=ScheduledZoneRuns(
                current_run=ScheduledZoneRun(
                    remaining_time=timedelta(seconds=1788),
                ),
            ),
        ),
    ]


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock ConfigEntry."""
    return MockConfigEntry(
        title="Hydrawise",
        domain=DOMAIN,
        data={
            CONF_API_KEY: "abc123",
        },
        unique_id="hydrawise-customerid",
    )


@pytest.fixture
async def mock_added_config_entry(
    mock_add_config_entry: Callable[[], Awaitable[MockConfigEntry]],
) -> MockConfigEntry:
    """Mock ConfigEntry that's been added to HA."""
    return await mock_add_config_entry()


@pytest.fixture
async def mock_add_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pydrawise: AsyncMock,
) -> Callable[[], Awaitable[MockConfigEntry]]:
    """Callable that creates a mock ConfigEntry that's been added to HA."""

    async def callback() -> MockConfigEntry:
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert DOMAIN in hass.config_entries.async_domains()
        return mock_config_entry

    return callback
