"""bosch_shc session fixtures."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.bosch_shc.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

# Every collection the integration reads off ``session.device_helper`` during
# setup. Tests inject devices into the relevant list before calling
# ``setup_integration``; everything else stays empty.
DEVICE_HELPER_COLLECTIONS = (
    "camera_360",
    "camera_eyes",
    "camera_outdoor_gen2",
    "climate_controls",
    "heating_circuits",
    "hue_lights",
    "ledvance_lights",
    "light_switches_bsm",
    "micromodule_blinds",
    "micromodule_dimmers",
    "micromodule_impulse_relays",
    "micromodule_light_attached",
    "micromodule_light_controls",
    "micromodule_relays",
    "micromodule_shutter_controls",
    "motion_detectors",
    "motion_detectors2",
    "presence_simulation_system",
    "roomthermostats",
    "shutter_contacts",
    "shutter_contacts2",
    "shutter_controls",
    "smart_plugs",
    "smart_plugs_compact",
    "smoke_detection_system",
    "smoke_detectors",
    "thermostats",
    "twinguards",
    "universal_switches",
    "wallthermostats",
    "water_leakage_detectors",
)


def make_device(
    device_id: str = "device-1",
    name: str = "Test device",
    **attrs: object,
) -> MagicMock:
    """Build a mock SHC device with the attributes the entity base needs."""
    device = MagicMock()
    device.id = device_id
    device.name = name
    device.serial = device_id
    device.root_device_id = "shc-root"
    device.device_model = "TEST_MODEL"
    device.manufacturer = "BOSCH"
    device.deleted = False
    device.device_services = []
    device.room_id = "room-1"
    for key, value in attrs.items():
        setattr(device, key, value)
    return device


@pytest.fixture(autouse=True)
def bosch_shc_mock_async_zeroconf(mock_async_zeroconf: MagicMock) -> None:
    """Auto mock zeroconf."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked Bosch SHC config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="shc012345",
        unique_id="test-mac",
        entry_id="01JE69BM3MA48YE6RH05A4MDKQ",
        data={
            CONF_HOST: "1.1.1.1",
            "ssl_certificate": "/etc/bosch_shc/test-cert.pem",
            "ssl_key": "/etc/bosch_shc/test-key.pem",
            CONF_TOKEN: "abc:test-mac",
            "hostname": "test-mac",
        },
    )


@pytest.fixture
def mock_device_helper() -> MagicMock:
    """Return a device_helper whose collections are all empty by default."""
    helper = MagicMock()
    for collection in DEVICE_HELPER_COLLECTIONS:
        setattr(helper, collection, [])
    return helper


@pytest.fixture
def mock_session(mock_device_helper: MagicMock) -> MagicMock:
    """Return a mocked SHCSessionAsync."""
    session = MagicMock()
    session.device_helper = mock_device_helper
    # _AsyncSHCInformation only exposes these attributes (no updateState).
    session.information = MagicMock(spec=["unique_id", "name", "version"])
    session.information.unique_id = "test-mac"
    session.information.name = "Bosch SHC"
    session.information.version = "10.0.0"
    # Singletons the integration always reads (every SHC has them).
    session.intrusion_system = make_device("intrusion", "Intrusion Detection System")
    session.emma = make_device("emma", "EMMA")
    session.scenarios = []
    session.userdefinedstates = []
    session.rooms = []
    session.devices = []
    session.async_init = AsyncMock()
    session.start_polling = AsyncMock()
    session.stop_polling = AsyncMock()
    session.subscribe_scenario_callback = MagicMock()
    session.unsubscribe_scenario_callback = MagicMock()
    return session


@pytest.fixture
def mock_setup_dependencies(mock_session: MagicMock) -> Generator[MagicMock]:
    """Patch certificate parsing, ssl-context build and the SHC session."""
    cert_info = MagicMock()
    cert_info.days_remaining = 365
    cert_info.not_after = MagicMock()
    with (
        patch(
            "homeassistant.components.bosch_shc.parse_certificate",
            return_value=cert_info,
        ),
        patch(
            "homeassistant.components.bosch_shc.build_ssl_context",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.bosch_shc.SHCSessionAsync",
            return_value=mock_session,
        ),
    ):
        yield mock_session


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Add the config entry and set up the integration."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
