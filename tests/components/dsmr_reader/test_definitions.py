"""Test the DSMR Reader definitions."""

import pytest

from homeassistant.components.dsmr_reader.const import DOMAIN
from homeassistant.components.dsmr_reader.definitions import (
    DSMRReaderSensorEntityDescription,
    dsmr_transform,
    tariff_transform,
)
from homeassistant.components.dsmr_reader.sensor import DSMRSensor
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_mqtt_message


@pytest.mark.parametrize(
    ("input", "expected"),
    [
        ("20", 2.0),
        ("version 5", "version 5"),
    ],
)
async def test_dsmr_transform(input, expected) -> None:
    """Test the dsmr_transform function."""
    assert dsmr_transform(input) == expected


@pytest.mark.parametrize(
    ("input", "expected"),
    [
        ("1", "low"),
        ("0", "high"),
    ],
)
async def test_tariff_transform(input, expected) -> None:
    """Test the tariff_transform function."""
    assert tariff_transform(input) == expected


@pytest.mark.usefixtures("mqtt_mock")
async def test_entity_tariff(hass: HomeAssistant) -> None:
    """Test the state attribute of DSMRReaderSensorEntityDescription when a tariff transform is needed."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DOMAIN,
        options={},
        entry_id="TEST_ENTRY_ID",
        unique_id="UNIQUE_TEST_ID",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Test if the payload is empty
    async_fire_mqtt_message(hass, "dsmr/meter-stats/electricity_tariff", "")
    await hass.async_block_till_done()

    electricity_tariff = "sensor.dsmr_meter_stats_electricity_tariff"
    assert hass.states.get(electricity_tariff).state == STATE_UNKNOWN

    # Test high tariff
    async_fire_mqtt_message(hass, "dsmr/meter-stats/electricity_tariff", "0")
    await hass.async_block_till_done()
    assert hass.states.get(electricity_tariff).state == "high"

    # Test low tariff
    async_fire_mqtt_message(hass, "dsmr/meter-stats/electricity_tariff", "1")
    await hass.async_block_till_done()
    assert hass.states.get(electricity_tariff).state == "low"


@pytest.mark.usefixtures("mqtt_mock")
async def test_entity_dsmr_transform(hass: HomeAssistant) -> None:
    """Test the state attribute of DSMRReaderSensorEntityDescription when a dsmr transform is needed."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DOMAIN,
        options={},
        entry_id="TEST_ENTRY_ID",
        unique_id="UNIQUE_TEST_ID",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Create the entity, since it's not by default
    description = DSMRReaderSensorEntityDescription(
        key="dsmr/meter-stats/dsmr_version",
        name="version_test",
        state=dsmr_transform,
    )
    sensor = DSMRSensor(description, config_entry)
    sensor.hass = hass
    await sensor.async_added_to_hass()

    # Test dsmr version, if it's a digit
    async_fire_mqtt_message(hass, "dsmr/meter-stats/dsmr_version", "42")
    await hass.async_block_till_done()

    dsmr_version = "sensor.dsmr_meter_stats_dsmr_version"
    assert hass.states.get(dsmr_version).state == "4.2"

    # Test dsmr version, if it's not a digit
    async_fire_mqtt_message(hass, "dsmr/meter-stats/dsmr_version", "version 5")
    await hass.async_block_till_done()

    assert hass.states.get(dsmr_version).state == "version 5"
