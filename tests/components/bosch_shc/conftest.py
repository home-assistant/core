"""bosch_shc session fixtures."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.bosch_shc.const import (
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def bosch_shc_mock_async_zeroconf(mock_async_zeroconf: MagicMock) -> None:
    """Auto mock zeroconf."""


# Every device_helper bucket any bosch_shc platform reads, defaulted to
# empty so a test only creates entities for the bucket(s) it explicitly
# passes to setup_integration().
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


async def setup_integration(
    hass: HomeAssistant,
    platforms: list[Platform],
    **device_buckets: list[SimpleNamespace],
) -> MockConfigEntry:
    """Set up bosch_shc restricted to platforms, with the given device_helper buckets."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_SSL_CERTIFICATE: "cert",
            CONF_SSL_KEY: "key",
        },
        unique_id="test-mac",
    )
    entry.add_to_hass(hass)

    mock_session = MagicMock()
    mock_session.information.unique_id = "test-mac"
    mock_session.information.updateState.name = "UP_TO_DATE"
    mock_session.information.version = "2.0"
    mock_session.device_helper = SimpleNamespace(
        **{**_EMPTY_DEVICE_BUCKETS, **device_buckets}
    )

    with (
        patch(
            "homeassistant.components.bosch_shc.SHCSession", return_value=mock_session
        ),
        patch("homeassistant.components.bosch_shc.PLATFORMS", platforms),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
