"""bosch_shc session fixtures."""

from __future__ import annotations

from collections.abc import Generator
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, create_autospec, patch

from boschshcpy import SHCBatteryDevice, SHCShutterContact
import pytest

from homeassistant.components.bosch_shc.const import (
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    DOMAIN,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

BATTERY_OK = SHCBatteryDevice.BatteryLevelService.State.OK


@pytest.fixture(autouse=True)
def bosch_shc_mock_async_zeroconf(mock_async_zeroconf: MagicMock) -> None:
    """Auto mock zeroconf."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock bosch_shc config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_SSL_CERTIFICATE: "cert",
            CONF_SSL_KEY: "key",
        },
        unique_id="test-mac",
    )


# Keep in sync with every platform's device_helper buckets — a bucket
# missing here breaks the mock_session fixture for whichever test needs it.
_EMPTY_DEVICE_BUCKETS: dict[str, list[Any]] = {
    bucket: []
    for bucket in (
        "camera_360",
        "camera_eyes",
        "light_switches_bsm",
        "motion_detectors",
        "shutter_contacts",
        "shutter_contacts2",
        "shutter_controls",
        "smart_plugs",
        "smart_plugs_compact",
        "smoke_detectors",
        "thermostats",
        "twinguards",
        "universal_switches",
        "wallthermostats",
        "water_leakage_detectors",
    )
}


@pytest.fixture
def device_buckets(request: pytest.FixtureRequest) -> dict[str, list[Any]]:
    """device_helper buckets for the mock session.

    Empty by default; a test overrides specific buckets via
    ``@pytest.mark.parametrize("device_buckets", [{...}], indirect=True)``.
    """
    overrides: dict[str, list[Any]] = getattr(request, "param", {})
    return {**_EMPTY_DEVICE_BUCKETS, **overrides}


@pytest.fixture
def mock_session(device_buckets: dict[str, list[Any]]) -> Generator[MagicMock]:
    """Mock SHCSession, patched in for the duration of the test."""
    session = MagicMock()
    session.information.unique_id = "test-mac"
    session.information.updateState.name = "UP_TO_DATE"
    session.information.version = "2.0"
    session.device_helper = SimpleNamespace(**device_buckets)
    with patch("homeassistant.components.bosch_shc.SHCSession", return_value=session):
        yield session


async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the bosch_shc integration for testing."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


def shutter_contact_device(
    device_id: str = "hdm:HomeMaticIP:contact1",
    name: str = "Contact",
    device_class: str = "ENTRANCE_DOOR",
    state: SHCShutterContact.ShutterContactService.State = (
        SHCShutterContact.ShutterContactService.State.CLOSED
    ),
    batterylevel: SHCBatteryDevice.BatteryLevelService.State = BATTERY_OK,
) -> SHCShutterContact:
    """Build a minimal shutter-contact device double.

    Shared across platform test files — a shutter contact also exposes a
    battery sensor, so both binary_sensor and sensor tests build on this.
    """
    device = create_autospec(SHCShutterContact, instance=True, spec_set=True)
    device.name = name
    device.id = device_id
    device.root_device_id = "test-mac"
    device.serial = f"serial-{device_id}"
    device.device_class = device_class
    device.state = state
    device.batterylevel = batterylevel
    device.device_services = []
    device.manufacturer = "Bosch"
    device.device_model = "SWD"
    device.status = "AVAILABLE"
    device.deleted = False
    return device


def battery_only_device(
    device_id: str = "hdm:HomeMaticIP:motion1",
    name: str = "Motion",
    batterylevel: SHCBatteryDevice.BatteryLevelService.State = BATTERY_OK,
) -> SHCBatteryDevice:
    """Build a minimal device double for a battery-only bucket.

    Shared across platform test files (e.g. motion_detectors, smoke_detectors,
    thermostats — every bucket that only ever contributes a battery sensor).
    """
    device = create_autospec(SHCBatteryDevice, instance=True, spec_set=True)
    device.name = name
    device.id = device_id
    device.root_device_id = "test-mac"
    device.serial = f"serial-{device_id}"
    device.batterylevel = batterylevel
    device.device_services = []
    device.manufacturer = "Bosch"
    device.device_model = "MD"
    device.status = "AVAILABLE"
    device.deleted = False
    return device
