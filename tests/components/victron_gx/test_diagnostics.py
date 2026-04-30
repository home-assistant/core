"""Tests for victron_gx diagnostics."""

from syrupy.assertion import SnapshotAssertion
from victron_mqtt import Hub as VictronVenusHub
from victron_mqtt.testing import finalize_injection, inject_message

from homeassistant.core import HomeAssistant

from .const import MOCK_INSTALLATION_ID

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    victron_hub, config_entry = init_integration

    latitude = "52.0907"
    longitude = "5.1214"

    # Inject metrics so the device tree is populated and enum serialization is covered
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/battery/0/Dc/0/Current",
        '{"value": 10.5}',
    )
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/system/0/SystemState/State",
        '{"value": 3}',
    )
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/gps/0/Position/Latitude",
        f'{{"value": {latitude}}}',
    )
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/gps/0/Position/Longitude",
        f'{{"value": {longitude}}}',
    )

    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    serialized_result = repr(result)

    assert latitude not in serialized_result
    assert longitude not in serialized_result
    assert "**REDACTED**" in serialized_result
    assert result == snapshot
