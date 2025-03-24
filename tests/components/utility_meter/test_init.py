"""The tests for the utility_meter component."""

from __future__ import annotations

from datetime import timedelta

from freezegun import freeze_time
import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.utility_meter import (
    select as um_select,
    sensor as um_sensor,
)
from homeassistant.components.utility_meter.const import DOMAIN, SERVICE_RESET
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_PLATFORM,
    EVENT_HOMEASSISTANT_START,
    Platform,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, mock_restore_cache


async def test_restore_state(hass: HomeAssistant) -> None:
    """Test utility sensor restore state."""
    config = {
        "utility_meter": {
            "energy_bill": {
                "source": "sensor.energy",
                "tariffs": ["onpeak", "midpeak", "offpeak"],
            }
        }
    }
    mock_restore_cache(
        hass,
        [
            State(
                "select.energy_bill",
                "midpeak",
            ),
        ],
    )

    assert await async_setup_component(hass, DOMAIN, config)
    assert await async_setup_component(hass, Platform.SENSOR, config)
    await hass.async_block_till_done()

    # restore from cache
    state = hass.states.get("select.energy_bill")
    assert state.state == "midpeak"


@pytest.mark.parametrize(
    "meter",
    [
        ["select.energy_bill"],
        "select.energy_bill",
    ],
)
async def test_services(hass: HomeAssistant, meter) -> None:
    """Test energy sensor reset service."""
    config = {
        "utility_meter": {
            "energy_bill": {
                "source": "sensor.energy",
                "cycle": "hourly",
                "tariffs": ["peak", "offpeak"],
            },
            "energy_bill2": {
                "source": "sensor.energy",
                "cycle": "hourly",
                "tariffs": ["peak", "offpeak"],
            },
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    assert await async_setup_component(hass, Platform.SENSOR, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    entity_id = config[DOMAIN]["energy_bill"]["source"]
    hass.states.async_set(
        entity_id, 1, {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR}
    )
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=10)
    with freeze_time(now):
        hass.states.async_set(
            entity_id,
            3,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_peak")
    assert state.state == "2"

    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state.state == "0"

    # Change tariff
    data = {ATTR_ENTITY_ID: "select.energy_bill", ATTR_OPTION: "offpeak"}
    await hass.services.async_call(SELECT_DOMAIN, SERVICE_SELECT_OPTION, data)
    await hass.async_block_till_done()

    now += timedelta(seconds=10)
    with freeze_time(now):
        hass.states.async_set(
            entity_id,
            4,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_peak")
    assert state.state == "2"

    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state.state == "1"

    # Change tariff
    data = {ATTR_ENTITY_ID: "select.energy_bill", "option": "wrong_tariff"}
    await hass.services.async_call(SELECT_DOMAIN, SERVICE_SELECT_OPTION, data)
    await hass.async_block_till_done()

    # Inexisting tariff, ignoring
    assert hass.states.get("select.energy_bill").state != "wrong_tariff"

    data = {ATTR_ENTITY_ID: "select.energy_bill", "option": "peak"}
    await hass.services.async_call(SELECT_DOMAIN, SERVICE_SELECT_OPTION, data)
    await hass.async_block_till_done()

    now += timedelta(seconds=10)
    with freeze_time(now):
        hass.states.async_set(
            entity_id,
            5,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_peak")
    assert state.state == "3"

    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state.state == "1"

    # Reset meters
    data = {ATTR_ENTITY_ID: meter}
    await hass.services.async_call(DOMAIN, SERVICE_RESET, data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_peak")
    assert state.state == "0"

    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state.state == "0"

    # meanwhile energy_bill2_peak accumulated all kWh
    state = hass.states.get("sensor.energy_bill2_peak")
    assert state.state == "4"


async def test_services_config_entry(hass: HomeAssistant) -> None:
    """Test energy sensor reset service."""
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "cycle": "monthly",
            "delta_values": False,
            "name": "Energy bill",
            "net_consumption": False,
            "offset": 0,
            "periodically_resetting": True,
            "source": "sensor.energy",
            "tariffs": ["peak", "offpeak"],
        },
        title="Energy bill",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "cycle": "monthly",
            "delta_values": False,
            "name": "Energy bill2",
            "net_consumption": False,
            "offset": 0,
            "periodically_resetting": True,
            "source": "sensor.energy",
            "tariffs": ["peak", "offpeak"],
        },
        title="Energy bill2",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    entity_id = "sensor.energy"
    hass.states.async_set(
        entity_id, 1, {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR}
    )
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=10)
    with freeze_time(now):
        hass.states.async_set(
            entity_id,
            3,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_peak")
    assert state.state == "2"

    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state.state == "0"

    # Change tariff
    data = {ATTR_ENTITY_ID: "select.energy_bill", "option": "offpeak"}
    await hass.services.async_call(SELECT_DOMAIN, SERVICE_SELECT_OPTION, data)
    await hass.async_block_till_done()

    now += timedelta(seconds=10)
    with freeze_time(now):
        hass.states.async_set(
            entity_id,
            4,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_peak")
    assert state.state == "2"

    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state.state == "1"

    # Change tariff
    data = {ATTR_ENTITY_ID: "select.energy_bill", "option": "wrong_tariff"}
    await hass.services.async_call(SELECT_DOMAIN, SERVICE_SELECT_OPTION, data)
    await hass.async_block_till_done()

    # Inexisting tariff, ignoring
    assert hass.states.get("select.energy_bill").state != "wrong_tariff"

    data = {ATTR_ENTITY_ID: "select.energy_bill", "option": "peak"}
    await hass.services.async_call(SELECT_DOMAIN, SERVICE_SELECT_OPTION, data)
    await hass.async_block_till_done()

    now += timedelta(seconds=10)
    with freeze_time(now):
        hass.states.async_set(
            entity_id,
            5,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_peak")
    assert state.state == "3"

    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state.state == "1"

    # Reset meters
    data = {ATTR_ENTITY_ID: "select.energy_bill"}
    await hass.services.async_call(DOMAIN, SERVICE_RESET, data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_peak")
    assert state.state == "0"

    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state.state == "0"

    # meanwhile energy_bill2_peak accumulated all kWh
    state = hass.states.get("sensor.energy_bill2_peak")
    assert state.state == "4"


async def test_cron(hass: HomeAssistant) -> None:
    """Test cron pattern."""

    config = {
        "utility_meter": {
            "energy_bill": {
                "source": "sensor.energy",
                "cron": "*/5 * * * *",
            }
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)


async def test_cron_and_meter(hass: HomeAssistant) -> None:
    """Test cron pattern and meter type fails."""
    config = {
        "utility_meter": {
            "energy_bill": {
                "source": "sensor.energy",
                "cycle": "hourly",
                "cron": "0 0 1 * *",
            }
        }
    }

    assert not await async_setup_component(hass, DOMAIN, config)


async def test_both_cron_and_meter(hass: HomeAssistant) -> None:
    """Test cron pattern and meter type passes in different meter."""
    config = {
        "utility_meter": {
            "energy_bill": {
                "source": "sensor.energy",
                "cron": "0 0 1 * *",
            },
            "water_bill": {
                "source": "sensor.water",
                "cycle": "hourly",
            },
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()


async def test_cron_and_offset(hass: HomeAssistant) -> None:
    """Test cron pattern and offset fails."""

    config = {
        "utility_meter": {
            "energy_bill": {
                "source": "sensor.energy",
                "offset": {"days": 1},
                "cron": "0 0 1 * *",
            }
        }
    }

    assert not await async_setup_component(hass, DOMAIN, config)


async def test_bad_cron(hass: HomeAssistant) -> None:
    """Test bad cron pattern."""

    config = {
        "utility_meter": {"energy_bill": {"source": "sensor.energy", "cron": "*"}}
    }

    assert not await async_setup_component(hass, DOMAIN, config)


async def test_setup_missing_discovery(hass: HomeAssistant) -> None:
    """Test setup with configuration missing discovery_info."""
    assert not await um_select.async_setup_platform(hass, {CONF_PLATFORM: DOMAIN}, None)
    assert not await um_sensor.async_setup_platform(hass, {CONF_PLATFORM: DOMAIN}, None)


@pytest.mark.parametrize(
    ("tariffs", "expected_entities"),
    [
        (
            [],
            ["sensor.electricity_meter"],
        ),
        (
            ["high", "low"],
            [
                "sensor.electricity_meter_low",
                "sensor.electricity_meter_high",
                "select.electricity_meter",
            ],
        ),
    ],
)
async def test_setup_and_remove_config_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    tariffs: str,
    expected_entities: list[str],
) -> None:
    """Test setting up and removing a config entry."""
    input_sensor_entity_id = "sensor.input"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "cycle": "monthly",
            "delta_values": False,
            "name": "Electricity meter",
            "net_consumption": False,
            "offset": 0,
            "periodically_resetting": True,
            "source": input_sensor_entity_id,
            "tariffs": tariffs,
        },
        title="Electricity meter",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == len(expected_entities)
    assert len(entity_registry.entities) == len(expected_entities)
    for entity in expected_entities:
        assert hass.states.get(entity)
        assert entity in entity_registry.entities

    # Remove the config entry
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are removed
    assert len(hass.states.async_all()) == 0
    assert len(entity_registry.entities) == 0


async def test_device_cleaning(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for source entity device for Utility Meter."""

    # Source entity device config entry
    source_config_entry = MockConfigEntry()
    source_config_entry.add_to_hass(hass)

    # Device entry of the source entity
    source_device1_entry = device_registry.async_get_or_create(
        config_entry_id=source_config_entry.entry_id,
        identifiers={("sensor", "identifier_test1")},
        connections={("mac", "30:31:32:33:34:01")},
    )

    # Source entity registry
    source_entity = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source",
        config_entry=source_config_entry,
        device_id=source_device1_entry.id,
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get("sensor.test_source") is not None

    # Configure the configuration entry for Utility Meter
    utility_meter_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "cycle": "monthly",
            "delta_values": False,
            "name": "Meter",
            "net_consumption": False,
            "offset": 0,
            "periodically_resetting": True,
            "source": "sensor.test_source",
            "tariffs": [],
        },
        title="Meter",
    )
    utility_meter_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(utility_meter_config_entry.entry_id)
    await hass.async_block_till_done()

    # Confirm the link between the source entity device and the meter sensor
    utility_meter_entity = entity_registry.async_get("sensor.meter")
    assert utility_meter_entity is not None
    assert utility_meter_entity.device_id == source_entity.device_id

    # Device entry incorrectly linked to Utility Meter config entry
    device_registry.async_get_or_create(
        config_entry_id=utility_meter_config_entry.entry_id,
        identifiers={("sensor", "identifier_test2")},
        connections={("mac", "30:31:32:33:34:02")},
    )
    device_registry.async_get_or_create(
        config_entry_id=utility_meter_config_entry.entry_id,
        identifiers={("sensor", "identifier_test3")},
        connections={("mac", "30:31:32:33:34:03")},
    )
    await hass.async_block_till_done()

    # Before reloading the config entry, two devices are expected to be linked
    devices_before_reload = device_registry.devices.get_devices_for_config_entry_id(
        utility_meter_config_entry.entry_id
    )
    assert len(devices_before_reload) == 3

    # Config entry reload
    await hass.config_entries.async_reload(utility_meter_config_entry.entry_id)
    await hass.async_block_till_done()

    # Confirm the link between the source entity device and the meter sensor after reload
    utility_meter_entity = entity_registry.async_get("sensor.meter")
    assert utility_meter_entity is not None
    assert utility_meter_entity.device_id == source_entity.device_id

    # After reloading the config entry, only one linked device is expected
    devices_after_reload = device_registry.devices.get_devices_for_config_entry_id(
        utility_meter_config_entry.entry_id
    )
    assert len(devices_after_reload) == 1
