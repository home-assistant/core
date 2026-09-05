"""Test the Tesla Fleet Diagnostics."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import setup_platform

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


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


async def test_diagnostics_without_location_scope(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    readonly_config_entry: MockConfigEntry,
) -> None:
    """Test charge schedule coordinates are withheld without the location scope."""

    await setup_platform(hass, readonly_config_entry)

    diag = await get_diagnostics_for_config_entry(
        hass, hass_client, readonly_config_entry
    )
    data = diag["vehicles"][0]["data"]

    for schedule in data["charge_schedule_data_charge_schedules"]:
        assert "latitude" not in schedule
        assert "longitude" not in schedule
    assert "charge_schedule_data_charge_schedule_window_latitude" not in data
    assert "charge_schedule_data_charge_schedule_window_longitude" not in data
