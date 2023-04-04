"""Test the SFR Box binary sensors."""
from collections.abc import Generator
from unittest.mock import patch

import pytest
from sfrbox_api.models import SystemInfo
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import assert_registries_and_states_for_config_entry

pytestmark = pytest.mark.usefixtures(
    "system_get_info", "dsl_get_info", "ftth_get_info", "wan_get_info"
)


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None, None, None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.sfr_box.PLATFORMS", [Platform.BINARY_SENSOR]):
        yield


@pytest.mark.parametrize("net_infra", ["adsl", "ftth"])
async def test_binary_sensors(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    snapshot: SnapshotAssertion,
    system_get_info: SystemInfo,
    net_infra: str,
) -> None:
    """Test for SFR Box binary sensors."""
    system_get_info.net_infra = net_infra
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await assert_registries_and_states_for_config_entry(hass, config_entry, snapshot)
