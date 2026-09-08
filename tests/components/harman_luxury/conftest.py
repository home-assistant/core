"""Common fixtures for the Harman Luxury tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aioharmanluxury import DeviceInfo, HarmanLuxuryState
import pytest

from homeassistant.components.harman_luxury.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_MANUFACTURER,
    ATTR_UPNP_SERIAL,
    SsdpServiceInfo,
)

from tests.common import MockConfigEntry

TEST_HOST = "1.2.3.4"
TEST_SERIAL = "48b782c2-60ac-40c1-a169-8d7ccb81dcc1"
TEST_NAME = "Dining Room"

DEVICE_INFO = DeviceInfo(
    serial=TEST_SERIAL,
    model="ARCAM ST5",
    name=TEST_NAME,
    mac="02:FE:6C:B7:EB:59",
)

PLAYER_STATE = HarmanLuxuryState(
    online=True,
    volume=45,
    muted=False,
    play_state="playing",
    title="Necessary Evil",
    artist="Motionless In White",
    album="Graveyard Shift",
    art_url="http://1.2.3.4/art.jpg",
    duration=228,
    position=42,
    can_play=True,
    can_pause=True,
    can_stop=True,
    can_next=True,
    can_previous=True,
)

SSDP_DISCOVERY = SsdpServiceInfo(
    ssdp_usn=f"uuid:{TEST_SERIAL}",
    ssdp_st="urn:schemas-upnp-org:device:MediaRenderer:1",
    ssdp_location=f"http://{TEST_HOST}:16500/desc.xml",
    upnp={
        ATTR_UPNP_SERIAL: TEST_SERIAL,
        ATTR_UPNP_MANUFACTURER: "Harman Luxury Audio",
    },
)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TEST_NAME,
        data={CONF_HOST: TEST_HOST},
        unique_id=TEST_SERIAL,
    )


@pytest.fixture
def mock_client() -> Generator[AsyncMock]:
    """Mock the Harman Luxury client."""
    with (
        patch(
            "homeassistant.components.harman_luxury.HarmanLuxuryClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.harman_luxury.config_flow.HarmanLuxuryClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.async_get_info.return_value = DEVICE_INFO
        client.async_get_state.return_value = PLAYER_STATE
        yield client
