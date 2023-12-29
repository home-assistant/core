"""The tests for Netgear LTE sensor platform."""
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant


async def test_sensors(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: None,
    setup_integration: None,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for successfully setting up the Netgear LTE sensor platform."""
    assert hass.states.get("sensor.netgear_lm1200_cell_id") == snapshot

    assert hass.states.get("sensor.netgear_lm1200_connection_text") == snapshot

    assert hass.states.get("sensor.netgear_lm1200_connection_type") == snapshot

    assert hass.states.get("sensor.netgear_lm1200_current_band") == snapshot

    assert hass.states.get("sensor.netgear_lm1200_service_type") == snapshot

    assert hass.states.get("sensor.netgear_lm1200_radio_quality") == snapshot

    assert hass.states.get("sensor.netgear_lm1200_register_network_display") == snapshot

    assert hass.states.get("sensor.netgear_lm1200_rx_level") == snapshot

    assert hass.states.get("sensor.netgear_lm1200_sms") == snapshot

    assert hass.states.get("sensor.netgear_lm1200_sms_total") == snapshot

    assert hass.states.get("sensor.netgear_lm1200_tx_level") == snapshot

    assert hass.states.get("sensor.netgear_lm1200_upstream") == snapshot

    assert hass.states.get("sensor.netgear_lm1200_usage") == snapshot
