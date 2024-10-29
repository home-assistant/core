"""Test the SFR Box diagnostics."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from sfrbox_api.models import SystemInfo
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

pytestmark = pytest.mark.usefixtures(
    "dsl_get_info", "ftth_get_info", "system_get_info", "wan_get_info"
)


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.sfr_box.PLATFORMS", []):
        yield


@pytest.mark.parametrize("net_infra", ["adsl", "ftth"])
async def test_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    system_get_info: SystemInfo,
    net_infra: str,
) -> None:
    """Test config entry diagnostics."""
    system_get_info.net_infra = net_infra
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )
