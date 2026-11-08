"""Test the Tesla Fleet Diagnostics."""

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import setup_platform


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Test diagnostics."""

    await setup_platform(hass, normal_config_entry)

    diag = await get_diagnostics_for_config_entry(
        hass, hass_client, normal_config_entry
    )
    assert diag == snapshot
