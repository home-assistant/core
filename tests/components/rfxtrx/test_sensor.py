"""The tests for the Rfxtrx sensor platform."""

import pytest

from homeassistant.components.rfxtrx import DOMAIN
from homeassistant.components.rfxtrx.const import ATTR_EVENT
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, State

from .conftest import create_rfx_test_cfg

from tests.common import MockConfigEntry, mock_restore_cache


async def test_default_config(hass: HomeAssistant, rfxtrx) -> None:
    """Test with 0 sensor."""
    entry_data = create_rfx_test_cfg(devices={})
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0


async def test_one_sensor(hass: HomeAssistant, rfxtrx) -> None:
    """Test with 1 sensor."""
    entry_data = create_rfx_test_cfg(devices={"0a52080705020095220269": {}})
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.wt260_wt260h_wt440h_wt450_wt450h_05_02_temperature")
    assert state
    assert state.state == "unknown"
    assert (
        state.attributes.get("friendly_name")
        == "WT260,WT260H,WT440H,WT450,WT450H 05:02 Temperature"
    )
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS


@pytest.mark.parametrize(
    ("state", "event"),
    [("18.4", "0a520801070100b81b0279"), ("17.9", "0a52085e070100b31b0279")],
)
async def test_state_restore(hass: HomeAssistant, rfxtrx, state, event) -> None:
    """State restoration."""

    entity_id = "sensor.wt260_wt260h_wt440h_wt450_wt450h_07_01_temperature"

    mock_restore_cache(hass, [State(entity_id, state, attributes={ATTR_EVENT: event})])

    entry_data = create_rfx_test_cfg(devices={"0a520801070100b81b0279": {}})
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == state


async def test_one_sensor_no_datatype(hass: HomeAssistant, rfxtrx) -> None:
    """Test with 1 sensor."""
    entry_data = create_rfx_test_cfg(devices={"0a52080705020095220269": {}})
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    base_id = "sensor.wt260_wt260h_wt440h_wt450_wt450h_05_02"
    base_name = "WT260,WT260H,WT440H,WT450,WT450H 05:02"

    state = hass.states.get(f"{base_id}_temperature")
    assert state
    assert state.state == "unknown"
    assert state.attributes.get("friendly_name") == f"{base_name} Temperature"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS

    state = hass.states.get(f"{base_id}_humidity")
    assert state
    assert state.state == "unknown"
    assert state.attributes.get("friendly_name") == f"{base_name} Humidity"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    state = hass.states.get(f"{base_id}_humidity_status")
    assert state
    assert state.state == "unknown"
    assert state.attributes.get("friendly_name") == f"{base_name} Humidity status"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None

    state = hass.states.get(f"{base_id}_signal_strength")
    assert state
    assert state.state == "unknown"
    assert state.attributes.get("friendly_name") == f"{base_name} Signal strength"
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    )

    state = hass.states.get(f"{base_id}_battery")
    assert state
    assert state.state == "unknown"
    assert state.attributes.get("friendly_name") == f"{base_name} Battery"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE


async def test_several_sensors(hass: HomeAssistant, rfxtrx) -> None:
    """Test with 3 sensors."""
    entry_data = create_rfx_test_cfg(
        devices={
            "0a52080705020095220269": {},
            "0a520802060100ff0e0269": {},
        }
    )
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    await hass.async_start()

    state = hass.states.get("sensor.wt260_wt260h_wt440h_wt450_wt450h_05_02_temperature")
    assert state
    assert state.state == "unknown"
    assert (
        state.attributes.get("friendly_name")
        == "WT260,WT260H,WT440H,WT450,WT450H 05:02 Temperature"
    )
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS

    state = hass.states.get("sensor.wt260_wt260h_wt440h_wt450_wt450h_06_01_temperature")
    assert state
    assert state.state == "unknown"
    assert (
        state.attributes.get("friendly_name")
        == "WT260,WT260H,WT440H,WT450,WT450H 06:01 Temperature"
    )
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS

    state = hass.states.get("sensor.wt260_wt260h_wt440h_wt450_wt450h_06_01_humidity")
    assert state
    assert state.state == "unknown"
    assert (
        state.attributes.get("friendly_name")
        == "WT260,WT260H,WT440H,WT450,WT450H 06:01 Humidity"
    )
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE


async def test_discover_sensor(hass: HomeAssistant, rfxtrx_automatic) -> None:
    """Test with discovery of sensor."""
    rfxtrx = rfxtrx_automatic

    # 1
    await rfxtrx.signal("0a520801070100b81b0279")
    base_id = "sensor.wt260_wt260h_wt440h_wt450_wt450h_07_01"

    state = hass.states.get(f"{base_id}_humidity")
    assert state
    assert state.state == "27"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    state = hass.states.get(f"{base_id}_humidity_status")
    assert state
    assert state.state == "normal"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None

    state = hass.states.get(f"{base_id}_signal_strength")
    assert state
    assert state.state == "-64"
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    )

    state = hass.states.get(f"{base_id}_temperature")
    assert state
    assert state.state == "18.4"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS

    state = hass.states.get(f"{base_id}_battery")
    assert state
    assert state.state == "100"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    # 2
    await rfxtrx.signal("0a52080405020095240279")
    base_id = "sensor.wt260_wt260h_wt440h_wt450_wt450h_05_02"
    state = hass.states.get(f"{base_id}_humidity")

    assert state
    assert state.state == "36"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    state = hass.states.get(f"{base_id}_humidity_status")
    assert state
    assert state.state == "normal"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None

    state = hass.states.get(f"{base_id}_signal_strength")
    assert state
    assert state.state == "-64"
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    )

    state = hass.states.get(f"{base_id}_temperature")
    assert state
    assert state.state == "14.9"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS

    state = hass.states.get(f"{base_id}_battery")
    assert state
    assert state.state == "100"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    # 1 Update
    await rfxtrx.signal("0a52085e070100b31b0279")
    base_id = "sensor.wt260_wt260h_wt440h_wt450_wt450h_07_01"

    state = hass.states.get(f"{base_id}_humidity")
    assert state
    assert state.state == "27"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    state = hass.states.get(f"{base_id}_humidity_status")
    assert state
    assert state.state == "normal"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None

    state = hass.states.get(f"{base_id}_signal_strength")
    assert state
    assert state.state == "-64"
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    )

    state = hass.states.get(f"{base_id}_temperature")
    assert state
    assert state.state == "17.9"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS

    state = hass.states.get(f"{base_id}_battery")
    assert state
    assert state.state == "100"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE

    assert len(hass.states.async_all()) == 10


async def test_update_of_sensors(hass: HomeAssistant, rfxtrx) -> None:
    """Test with 3 sensors."""
    entry_data = create_rfx_test_cfg(
        devices={
            "0a52080705020095220269": {},
            "0a520802060100ff0e0269": {},
        }
    )
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    await hass.async_start()

    state = hass.states.get("sensor.wt260_wt260h_wt440h_wt450_wt450h_05_02_temperature")
    assert state
    assert state.state == "unknown"

    state = hass.states.get("sensor.wt260_wt260h_wt440h_wt450_wt450h_06_01_temperature")
    assert state
    assert state.state == "unknown"

    state = hass.states.get("sensor.wt260_wt260h_wt440h_wt450_wt450h_06_01_humidity")
    assert state
    assert state.state == "unknown"

    await rfxtrx.signal("0a520802060101ff0f0269")
    await rfxtrx.signal("0a52080705020085220269")

    state = hass.states.get("sensor.wt260_wt260h_wt440h_wt450_wt450h_05_02_temperature")
    assert state
    assert state.state == "13.3"

    state = hass.states.get("sensor.wt260_wt260h_wt440h_wt450_wt450h_06_01_temperature")
    assert state
    assert state.state == "51.1"

    state = hass.states.get("sensor.wt260_wt260h_wt440h_wt450_wt450h_06_01_humidity")
    assert state
    assert state.state == "15"


async def test_rssi_sensor(hass: HomeAssistant, rfxtrx) -> None:
    """Test with 1 sensor."""
    entry_data = create_rfx_test_cfg(
        devices={
            "0913000022670e013b70": {
                "data_bits": 4,
                "command_on": 0xE,
                "command_off": 0x7,
            },
            "0b1100cd0213c7f230010f71": {},
        }
    )
    mock_entry = MockConfigEntry(domain="rfxtrx", unique_id=DOMAIN, data=entry_data)

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    await hass.async_start()

    state = hass.states.get("sensor.pt2262_22670e_signal_strength")
    assert state
    assert state.state == "unknown"
    assert state.attributes.get("friendly_name") == "PT2262 22670e Signal strength"
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    )

    state = hass.states.get("sensor.ac_213c7f2_48_signal_strength")
    assert state
    assert state.state == "unknown"
    assert state.attributes.get("friendly_name") == "AC 213c7f2:48 Signal strength"
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    )

    await rfxtrx.signal("0913000022670e013b70")
    await rfxtrx.signal("0b1100cd0213c7f230010f71")

    state = hass.states.get("sensor.pt2262_22670e_signal_strength")
    assert state
    assert state.state == "-64"

    state = hass.states.get("sensor.ac_213c7f2_48_signal_strength")
    assert state
    assert state.state == "-64"

    await rfxtrx.signal("0913000022670e013b60")
    await rfxtrx.signal("0b1100cd0213c7f230010f61")

    state = hass.states.get("sensor.pt2262_22670e_signal_strength")
    assert state
    assert state.state == "-72"

    state = hass.states.get("sensor.ac_213c7f2_48_signal_strength")
    assert state
    assert state.state == "-72"
