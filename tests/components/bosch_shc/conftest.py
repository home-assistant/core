"""bosch_shc session fixtures."""

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, create_autospec, patch

from boschshcpy.device_helper import SHCDeviceHelper
from boschshcpy.information import SHCInformation
from boschshcpy.session import SHCSession
import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DOMAIN = "bosch_shc"

MOCK_ENTRY_DATA = {
    "host": "1.2.3.4",
    "ssl_certificate": "/fake/cert.pem",
    "ssl_key": "/fake/key.pem",
    "hostname": "shc012345",
    "token": "token:shc012345",
}


@pytest.fixture(autouse=True)
def bosch_shc_mock_async_zeroconf(mock_async_zeroconf: MagicMock) -> None:
    """Auto mock zeroconf."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock bosch_shc config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data=MOCK_ENTRY_DATA,
        unique_id="shc012345",
        title="Test SHC",
    )


@pytest.fixture
def mock_session() -> MagicMock:
    """Return an autospecced SHCSession with all device lists empty.

    Autospeccing the session, information and device_helper catches typos in
    attribute/method names used by the integration; individual tests set the
    device_helper lists they need.
    """
    session = create_autospec(SHCSession, instance=True)
    session.information = create_autospec(SHCInformation, instance=True)
    session.information.unique_id = "shc-test-uid"
    session.information.version = "9.99"
    session.information.updateState.name = "UP_TO_DATE"
    session.scenarios = []
    session.device_helper = create_autospec(SHCDeviceHelper, instance=True)
    session.device_helper.micromodule_impulse_relays = []
    session.device_helper.smoke_detectors = []
    session.device_helper.twinguards = []
    session.device_helper.motion_detectors2 = []
    return session


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms to load; override in a test module to scope setup to one platform."""
    return []


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    platforms: list[Platform],
) -> AsyncGenerator[MockConfigEntry]:
    """Set up the bosch_shc integration with only the given platforms loaded."""
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSession",
            return_value=mock_session,
        ),
        patch("homeassistant.components.bosch_shc.async_get_instance"),
        patch("homeassistant.components.bosch_shc.PLATFORMS", platforms),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        yield mock_config_entry
