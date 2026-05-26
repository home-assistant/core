"""Test the qingpingiot switch entities."""

from homeassistant.components.qingpingiot.const import DOMAIN
from homeassistant.const import CONF_MAC, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.typing import MqttMockHAClient

MAC = "AABBCCDDEEFF"


async def test_switches_created_for_cgr1w(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test that expected switches are created for CGR1W model."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MAC,
        data={
            CONF_MAC: MAC,
            CONF_MODEL: "cgr1w",
            CONF_NAME: "Test Device",
        },
        title="Test Device",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_reg = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_reg, entry.entry_id)

    switch_entities = [
        e
        for e in entities
        if e.platform == DOMAIN
        and ("co2_asc" in e.unique_id or "led_indicator" in e.unique_id)
    ]

    assert len(switch_entities) == 2

    entity_keys = {e.unique_id for e in switch_entities}
    assert f"{MAC}_co2_asc" in entity_keys
    assert f"{MAC}_led_indicator" in entity_keys


async def test_switch_turn_on(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test turning on a switch."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MAC,
        data={
            CONF_MAC: MAC,
            CONF_MODEL: "cgr1w",
            CONF_NAME: "Test Device",
        },
        title="Test Device",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinator
    coordinator.data["online"] = True

    state = hass.states.get("switch.test_device_co2_auto_self_calibration")
    assert state is not None
    assert state.state == "on"

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.test_device_co2_auto_self_calibration"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_device_co2_auto_self_calibration")
    assert state.state == "off"


async def test_switch_default_value(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test switch defaults to on when no data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MAC,
        data={
            CONF_MAC: MAC,
            CONF_MODEL: "cgr1w",
            CONF_NAME: "Test Device",
        },
        title="Test Device",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinator
    coordinator.data["online"] = True

    state = hass.states.get("switch.test_device_rating_light")
    assert state is not None
    # Default is True for led_indicator
    assert state.state == "on"
