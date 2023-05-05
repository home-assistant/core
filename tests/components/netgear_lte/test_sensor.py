"""The tests for Netgear LTE sensor platform."""
from unittest.mock import AsyncMock

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfInformation,
)
from homeassistant.core import HomeAssistant

from .conftest import ComponentSetup


async def test_sensors(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    entity_registry_enabled_by_default: AsyncMock,
    connection,
):
    """Test for successfully setting up the Netgear LTE sensor platform."""
    await setup_integration()

    state = hass.states.get("sensor.netgear_lte_cell_id")
    assert state.state == "12345678"
    state = hass.states.get("sensor.netgear_lte_connection_text")
    assert state.state == "4G"
    state = hass.states.get("sensor.netgear_lte_connection_type")
    assert state.state == "IPv4AndIPv6"
    state = hass.states.get("sensor.netgear_lte_current_band")
    assert state.state == "LTE B4"
    state = hass.states.get("sensor.netgear_lte_current_ps_service_type")
    assert state.state == "LTE"
    state = hass.states.get("sensor.netgear_lte_radio_quality")
    assert state.state == "52"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    state = hass.states.get("sensor.netgear_lte_register_network_display")
    assert state.state == "T-Mobile"
    state = hass.states.get("sensor.netgear_lte_rx_level")
    assert state.state == "-113"
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    )
    state = hass.states.get("sensor.netgear_lte_sms")
    assert state.state == "1"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "unread"
    state = hass.states.get("sensor.netgear_lte_sms_total")
    assert state.state == "1"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "messages"
    state = hass.states.get("sensor.netgear_lte_tx_level")
    assert state.state == "4"
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    )
    state = hass.states.get("sensor.netgear_lte_upstream")
    assert state.state == "LTE"
    state = hass.states.get("sensor.netgear_lte_usage")
    assert state.state == "40.5"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfInformation.MEBIBYTES
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.DATA_SIZE
