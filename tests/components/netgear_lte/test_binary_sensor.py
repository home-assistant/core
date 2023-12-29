"""The tests for Netgear LTE binary sensor platform."""
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant


async def test_binary_sensors(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    setup_integration: None,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for successfully setting up the Netgear LTE binary sensor platform."""
    assert hass.states.get("binary_sensor.netgear_lm1200_mobile_connected") == snapshot

    assert hass.states.get("binary_sensor.netgear_lm1200_wire_connected") == snapshot

    assert hass.states.get("binary_sensor.netgear_lm1200_roaming") == snapshot
