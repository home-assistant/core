"""Fixtures for Baby Tracker (Nighp) tests.

The library's client is faked at its public interface by ``FakeServer`` (see ``fake_server.py``).
The real sync engine runs on top of the fake, so the tests exercise the real merging of logs.
"""

from collections.abc import Generator, Iterator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.baby_tracker.const import CONF_DEVICE_UUID, DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import (
    BABY_THREE,
    BABY_TWO,
    EMAIL,
    EMAIL_TWO,
    ENTRY_ID,
    OWN_DEVICE,
    PASSWORD,
    setup_integration,
)
from .factories import DEVICE_A, DEVICE_B, at, volume
from .fake_server import FakeClient, FakeServer


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry, so a config flow test doesn't set the integration up."""
    with patch(
        "homeassistant.components.baby_tracker.async_setup_entry",
        return_value=None,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def server() -> FakeServer:
    """A fake sync service with one phone that has logged for two babies."""
    server = FakeServer()
    server.names[DEVICE_A] = "Test Phone"
    server.add_record(
        DEVICE_A,
        "Diaper",
        "D0000000-0000-4000-8000-000000000001",
        when=at(0),
        status=0,
    )
    server.add_record(
        DEVICE_A,
        "Diaper",
        "D0000000-0000-4000-8000-000000000002",
        when=at(10),
        baby=BABY_TWO,
        status=1,
    )
    return server


@pytest.fixture
def second_server() -> FakeServer:
    """A second account's service, with one phone that has logged for a third baby."""
    server = FakeServer()
    server.names[DEVICE_B] = "Other Phone"
    server.add_record(
        DEVICE_B,
        "Diaper",
        "D0000000-0000-4000-8000-0000000000B1",
        when=at(3),
        baby=BABY_THREE,
        status=2,
    )
    return server


@pytest.fixture(autouse=True)
def mock_baby_tracker_client(
    server: FakeServer, second_server: FakeServer
) -> Iterator[FakeServer]:
    """Replace the library's client everywhere the integration builds one.

    It is autouse so that no test can reach the real service by accident.
    """

    def factory(email: str, *args: Any, **kwargs: Any) -> FakeClient:
        # The second account signs in to its own service, every other one to the first.
        return FakeClient(
            second_server if email == EMAIL_TWO else server, email, *args, **kwargs
        )

    with (
        patch("homeassistant.components.baby_tracker.BabyTrackerClient", factory),
        patch(
            "homeassistant.components.baby_tracker.config_flow.BabyTrackerClient",
            factory,
        ),
    ):
        yield server


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """The default entry: one account, with its unique ID set."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=EMAIL,
        unique_id=EMAIL,
        entry_id=ENTRY_ID,  # fixed, because the account sensor's unique ID is built from it
        data={
            CONF_EMAIL: EMAIL,
            CONF_PASSWORD: PASSWORD,
            CONF_DEVICE_UUID: OWN_DEVICE,
        },
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set the default entry up. Tests check the resulting state."""
    await setup_integration(hass, mock_config_entry)
    return mock_config_entry


@pytest.fixture
def populated_server(server: FakeServer) -> FakeServer:
    """The default server plus every kind of record a baby's entities read.

    Baby one has a feed of each kind, a sleep, and a pump (which belongs to the account). Baby two
    has a sleep still running. All of it falls on the same local day as ``at(180)``.
    """
    server.add_record(
        DEVICE_A,
        "Formula",
        "F0000000-0000-4000-8000-000000000001",
        when=at(20),
        amount=volume(4),
    )
    server.add_record(
        DEVICE_A,
        "Nursing",
        "F0000000-0000-4000-8000-000000000002",
        when=at(40),
        leftDuration=7,
        rightDuration=12,
        bothDuration=0,
        finishSide=1,
        note="invented note",
    )
    server.add_record(
        DEVICE_A,
        "Pumped",
        "F0000000-0000-4000-8000-000000000003",
        when=at(60),
        amount=volume(90, english=False),
    )
    server.add_record(
        DEVICE_A,
        "Sleep",
        "F0000000-0000-4000-8000-000000000004",
        when=at(90),
        duration=45,
        note="invented nap",
    )
    server.add_record(
        DEVICE_A,
        "Sleep",
        "F0000000-0000-4000-8000-000000000005",
        when=at(120),
        baby=BABY_TWO,
        duration=0,
    )
    return server
