"""Common fixtures for the ECHONET Lite integration tests."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from pyhems import EOJ
from pyhems.runtime import HemsFrameEvent
import pytest

from homeassistant.components.echonet_lite.const import (
    CONF_ENABLE_EXPERIMENTAL,
    CONF_INTERFACE,
    DEFAULT_INTERFACE,
    DOMAIN,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@dataclass(slots=True)
class TestProperty:
    """Minimal representation of an ECHONET Lite property for tests."""

    __test__ = False
    epc: int
    edt: bytes


@dataclass(slots=True)
class TestFrame:
    """Minimal representation of an ECHONET Lite frame for tests."""

    __test__ = False
    tid: int
    seoj: bytes
    deoj: bytes
    esv: int
    properties: list[TestProperty]

    def is_response_frame(self) -> bool:
        """Check if frame is a response (success or failure)."""
        return (0x70 <= self.esv <= 0x7F) or (0x50 <= self.esv <= 0x5F)


# Default manufacturer code for tests (arbitrary but consistent)
TEST_MANUFACTURER_CODE = 0x000005  # Sharp


def make_frame_event(
    frame,
    *,
    node_id: str,
    eoj: EOJ,
    received_at: float = 0.0,
) -> HemsFrameEvent:
    """Create a HemsFrameEvent for testing.

    All fields except received_at are required to match pyhems type guarantees.
    """
    return HemsFrameEvent(
        received_at=received_at,
        frame=frame,
        node_id=node_id,
        eoj=eoj,
    )


def make_property_map_edt(*epcs: int) -> bytes:
    """Create EDT bytes for a property map (0x9D/0x9E/0x9F).

    For property maps with 15 or fewer EPCs, the format is:
    - 1 byte: number of EPCs
    - N bytes: EPC values

    For property maps with 16+ EPCs, a bitmap format is used (not implemented here).
    """
    count = len(epcs)
    if count <= 15:
        return bytes([count, *epcs])

    # Bitmap format for 16+ EPCs covering EPCs 0x80-0xFF
    bitmap = [0] * 16
    for epc in epcs:
        if not 0x80 <= epc <= 0xFF:
            raise ValueError("EPC out of bitmap range (0x80-0xFF)")
        low = epc & 0x0F
        high = (epc >> 4) - 8  # 0 for 0x8x, 7 for 0xFx
        bitmap[low] |= 1 << high
    return bytes([count, *bitmap])


@pytest.fixture
def mock_async_validate_network() -> Generator[AsyncMock]:
    """Patch the multicast socket to avoid I/O during flows."""

    mock_protocol = MagicMock()
    mock_protocol.close = MagicMock()
    with (
        patch(
            "homeassistant.components.echonet_lite.config_flow.create_multicast_socket",
            AsyncMock(return_value=mock_protocol),
        ),
    ):
        yield mock_protocol


@pytest.fixture
def mock_echonet_lite_client() -> Generator[AsyncMock]:
    """Patch the runtime client used by the integration."""

    client = AsyncMock()
    client.start = AsyncMock()
    client.stop = AsyncMock()
    client.async_get = AsyncMock(return_value=[])
    client.async_request = AsyncMock()
    client.async_send = AsyncMock(return_value=True)

    def _subscribe(callback):
        # Wrap the provided callback in an AsyncMock so tests can always await
        # it regardless of whether the integration's callback is sync or async.
        async def _async_callback(event):
            return callback(event)

        client._listener = AsyncMock(side_effect=_async_callback)
        return lambda: None

    client.subscribe = Mock(side_effect=_subscribe)

    with patch("homeassistant.components.echonet_lite.HemsClient", return_value=client):
        yield client


@pytest.fixture
def mock_definitions_registry() -> Generator[None]:
    """Ensure definitions registry is loaded for tests.

    The definitions registry loads from the bundled JSON file automatically.
    No mocking is needed as long as device_definitions.json exists.
    """
    return


@pytest.fixture
def platforms() -> list[Platform]:
    """Return the list of platforms to set up for the integration."""

    return []


@pytest.fixture(autouse=True)
def patch_platforms(platforms: list[Platform]) -> Generator[None]:
    """Patch the PLATFORMS constant for each test."""

    with patch("homeassistant.components.echonet_lite.PLATFORMS", platforms):
        yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a default mocked config entry for the integration.

    By default, enable_experimental is True for testing non-stable device classes.
    """
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INTERFACE: DEFAULT_INTERFACE},
        options={CONF_ENABLE_EXPERIMENTAL: True},
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_echonet_lite_client: AsyncMock,
    mock_definitions_registry: None,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the integration in Home Assistant."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
