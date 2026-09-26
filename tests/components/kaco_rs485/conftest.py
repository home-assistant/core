"""Common fixtures for the KACO RS485 tests.

The bus double serves frames captured from real hardware, so these tests drive
the actual framing and parsing code rather than a mock.
"""

from collections.abc import Generator
from functools import partial
from unittest.mock import AsyncMock, patch

from kaco_rs485 import KacoRs485Client
from kaco_rs485.discovery import scan
from kaco_rs485.testing import FakeBus, a_bus
import pytest

from homeassistant.components.kaco_rs485.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import MOCK_ADDRESSES, MOCK_ENTRY_DATA, MOCK_PORT, MOCK_PORT_DESCRIPTION

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def no_bus_pacing() -> Generator[None]:
    """Remove the library's real-time pacing.

    Properties of a shared medium, exercised in the library's own tests.
    """
    with (
        patch(
            "homeassistant.components.kaco_rs485.config_flow.scan",
            partial(scan, poll_gap_s=0),
        ),
        patch(
            "homeassistant.components.kaco_rs485.coordinator.KacoRs485Client",
            partial(KacoRs485Client, poll_gap_s=0, sleep_retry_s=0),
        ),
    ):
        yield


@pytest.fixture
def mock_bus() -> Generator[FakeBus]:
    """Hand both the config flow and the coordinator one bus of captured frames."""
    fake_bus = a_bus(MOCK_ADDRESSES)
    with (
        patch(
            "homeassistant.components.kaco_rs485.config_flow.AsyncBus",
            return_value=fake_bus,
        ),
        patch(
            "homeassistant.components.kaco_rs485.coordinator.AsyncBus",
            return_value=fake_bus,
        ),
    ):
        yield fake_bus


@pytest.fixture(autouse=True)
def mock_serial_ports() -> Generator[AsyncMock]:
    """Name the port the way the `usb` integration would."""
    port = AsyncMock()
    port.device = MOCK_PORT
    port.description = MOCK_PORT_DESCRIPTION

    with patch(
        "homeassistant.components.kaco_rs485.config_flow.usb.async_scan_serial_ports",
        return_value=[port],
    ) as scan_ports:
        yield scan_ports


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Stop config-flow tests from setting the integration up for real."""
    with patch(
        "homeassistant.components.kaco_rs485.async_setup_entry",
        return_value=True,
    ) as setup_entry:
        yield setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A config entry describing the three-inverter bus."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_PORT_DESCRIPTION,
        data=MOCK_ENTRY_DATA,
        # Fixed: unique ids derive from it, so a random one breaks snapshots.
        entry_id="01JRS485KACOENTRYIDFORTESTS",
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_bus: FakeBus,
) -> MockConfigEntry:
    """Set the integration up against the fake bus."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
