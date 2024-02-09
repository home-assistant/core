"""Tests for myuplink diagnostics data."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


# testing
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    with patch(
        "homeassistant.components.myuplink.MyUplinkAPI.async_get_systems_json",
        return_value=load_fixture("myuplink/systems.json"),
    ), patch(
        "homeassistant.components.myuplink.MyUplinkAPI.async_get_device_json",
        return_value=load_fixture("myuplink/device.json"),
    ), patch(
        "homeassistant.components.myuplink.MyUplinkAPI.async_get_device_points_json",
        return_value=load_fixture("myuplink/device_points_nibe_f730.json"),
    ):
        snapshot.assert_match(
            await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        )
        # assert (
        #     await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        #     == snapshot
        # )
