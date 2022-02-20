"""The tests for the utility_meter component."""
from datetime import timedelta
from unittest.mock import patch

from homeassistant.components.utility_meter.const import (
    ATTR_TARIFF,
    DOMAIN,
    SERVICE_RESET,
    SERVICE_SELECT_NEXT_TARIFF,
    SERVICE_SELECT_TARIFF,
)
import homeassistant.components.utility_meter.sensor as um_sensor
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_PLATFORM,
    ENERGY_KILO_WATT_HOUR,
    EVENT_HOMEASSISTANT_START,
    Platform,
)
from homeassistant.core import State
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import mock_restore_cache


async def test_restore_state(hass):
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
                "utility_meter.energy_bill",
                "midpeak",
            ),
        ],
    )

    assert await async_setup_component(hass, DOMAIN, config)
    assert await async_setup_component(hass, Platform.SENSOR, config)
    await hass.async_block_till_done()

    # restore from cache
    state = hass.states.get("utility_meter.energy_bill")
    assert state.state == "midpeak"


async def test_services(hass):
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
        entity_id, 1, {ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR}
    )
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=10)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.states.async_set(
            entity_id,
            3,
            {ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_peak")
    assert state.state == "2"

    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state.state == "0"

    # Next tariff
    data = {ATTR_ENTITY_ID: "utility_meter.energy_bill"}
    await hass.services.async_call(DOMAIN, SERVICE_SELECT_NEXT_TARIFF, data)
    await hass.async_block_till_done()

    now += timedelta(seconds=10)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.states.async_set(
            entity_id,
            4,
            {ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_peak")
    assert state.state == "2"

    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state.state == "1"

    # Change tariff
    data = {ATTR_ENTITY_ID: "utility_meter.energy_bill", ATTR_TARIFF: "wrong_tariff"}
    await hass.services.async_call(DOMAIN, SERVICE_SELECT_TARIFF, data)
    await hass.async_block_till_done()

    # Inexisting tariff, ignoring
    assert hass.states.get("utility_meter.energy_bill").state != "wrong_tariff"

    data = {ATTR_ENTITY_ID: "utility_meter.energy_bill", ATTR_TARIFF: "peak"}
    await hass.services.async_call(DOMAIN, SERVICE_SELECT_TARIFF, data)
    await hass.async_block_till_done()

    now += timedelta(seconds=10)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.states.async_set(
            entity_id,
            5,
            {ATTR_UNIT_OF_MEASUREMENT: ENERGY_KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_peak")
    assert state.state == "3"

    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state.state == "1"

    # Reset meters
    data = {ATTR_ENTITY_ID: "utility_meter.energy_bill"}
    await hass.services.async_call(DOMAIN, SERVICE_RESET, data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_peak")
    assert state.state == "0"

    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state.state == "0"

    # meanwhile energy_bill2_peak accumulated all kWh
    state = hass.states.get("sensor.energy_bill2_peak")
    assert state.state == "4"


async def test_cron(hass, legacy_patchable_time):
    """Test cron pattern and offset fails."""

    config = {
        "utility_meter": {
            "energy_bill": {
                "source": "sensor.energy",
                "cron": "*/5 * * * *",
            }
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)


async def test_cron_and_meter(hass, legacy_patchable_time):
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


async def test_both_cron_and_meter(hass, legacy_patchable_time):
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


async def test_cron_and_offset(hass, legacy_patchable_time):
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


async def test_bad_cron(hass, legacy_patchable_time):
    """Test bad cron pattern."""

    config = {
        "utility_meter": {"energy_bill": {"source": "sensor.energy", "cron": "*"}}
    }

    assert not await async_setup_component(hass, DOMAIN, config)


async def test_setup_missing_discovery(hass):
    """Test setup with configuration missing discovery_info."""
    assert not await um_sensor.async_setup_platform(hass, {CONF_PLATFORM: DOMAIN}, None)
