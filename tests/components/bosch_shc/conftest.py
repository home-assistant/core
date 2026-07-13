"""bosch_shc session fixtures."""

from __future__ import annotations

from collections.abc import Generator
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from boschshcpy import SHCShutterControl
import pytest

from homeassistant.components.bosch_shc.const import (
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    DOMAIN,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

STOPPED = SHCShutterControl.ShutterControlService.State.STOPPED


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


def cover_device(
    device_id: str = "hdm:HomeMaticIP:cover1",
    level: float = 0.5,
    operation_state: SHCShutterControl.ShutterControlService.State = STOPPED,
) -> SimpleNamespace:
    """Build a minimal shutter-control device double."""
    return SimpleNamespace(
        name="Cover",
        id=device_id,
        root_device_id="test-mac",
        serial=f"serial-{device_id}",
        device_model="SWD",
        level=level,
        operation_state=operation_state,
        device_services=[],
        manufacturer="Bosch",
        status="AVAILABLE",
        deleted=False,
        stop=MagicMock(),
        subscribe_callback=MagicMock(),
        unsubscribe_callback=MagicMock(),
    )
