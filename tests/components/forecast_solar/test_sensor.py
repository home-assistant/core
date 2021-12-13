"""Tests for the sensors provided by the Forecast.Solar integration."""
from unittest.mock import MagicMock

import pytest

from homeassistant.components.forecast_solar.const import DOMAIN
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    STATE_CLASS_MEASUREMENT,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TIMESTAMP,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_sensors(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test the Forecast.Solar sensors."""
    entry_id = init_integration.entry_id
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    state = hass.states.get("sensor.energy_production_today")
    entry = entity_registry.async_get("sensor.energy_production_today")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_energy_production_today"
    assert state.state == "100.0"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Estimated Energy Production - Today"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ENERGY_KILO_WATT_HOUR
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_ENERGY
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.energy_production_tomorrow")
    entry = entity_registry.async_get("sensor.energy_production_tomorrow")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_energy_production_tomorrow"
    assert state.state == "200.0"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Estimated Energy Production - Tomorrow"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ENERGY_KILO_WATT_HOUR
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_ENERGY
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.power_highest_peak_time_today")
    entry = entity_registry.async_get("sensor.power_highest_peak_time_today")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_power_highest_peak_time_today"
    assert state.state == "2021-06-27T13:00:00+00:00"
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Highest Power Peak Time - Today"
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_TIMESTAMP
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.power_highest_peak_time_tomorrow")
    entry = entity_registry.async_get("sensor.power_highest_peak_time_tomorrow")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_power_highest_peak_time_tomorrow"
    assert state.state == "2021-06-27T14:00:00+00:00"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == "Highest Power Peak Time - Tomorrow"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_TIMESTAMP
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.power_production_now")
    entry = entity_registry.async_get("sensor.power_production_now")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_power_production_now"
    assert state.state == "300000"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME) == "Estimated Power Production - Now"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == STATE_CLASS_MEASUREMENT
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_POWER
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.energy_current_hour")
    entry = entity_registry.async_get("sensor.energy_current_hour")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_energy_current_hour"
    assert state.state == "800.0"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Estimated Energy Production - This Hour"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ENERGY_KILO_WATT_HOUR
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_ENERGY
    assert ATTR_ICON not in state.attributes

    state = hass.states.get("sensor.energy_next_hour")
    entry = entity_registry.async_get("sensor.energy_next_hour")
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_energy_next_hour"
    assert state.state == "900.0"
    assert (
        state.attributes.get(ATTR_FRIENDLY_NAME)
        == "Estimated Energy Production - Next Hour"
    )
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == ENERGY_KILO_WATT_HOUR
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_ENERGY
    assert ATTR_ICON not in state.attributes

    assert entry.device_id
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry
    assert device_entry.identifiers == {(DOMAIN, f"{entry_id}")}
    assert device_entry.manufacturer == "Forecast.Solar"
    assert device_entry.name == "Solar Production Forecast"
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE
    assert device_entry.model == "public"
    assert not device_entry.sw_version


@pytest.mark.parametrize(
    "entity_id",
    (
        "sensor.power_production_next_12hours",
        "sensor.power_production_next_24hours",
        "sensor.power_production_next_hour",
    ),
)
async def test_disabled_by_default(
    hass: HomeAssistant, init_integration: MockConfigEntry, entity_id: str
) -> None:
    """Test the Forecast.Solar sensors that are disabled by default."""
    entity_registry = er.async_get(hass)

    state = hass.states.get(entity_id)
    assert state is None

    entry = entity_registry.async_get(entity_id)
    assert entry
    assert entry.disabled
    assert entry.disabled_by == er.DISABLED_INTEGRATION


@pytest.mark.parametrize(
    "key,name,value",
    [
        (
            "power_production_next_12hours",
            "Estimated Power Production - Next 12 Hours",
            "600000",
        ),
        (
            "power_production_next_24hours",
            "Estimated Power Production - Next 24 Hours",
            "700000",
        ),
        (
            "power_production_next_hour",
            "Estimated Power Production - Next Hour",
            "400000",
        ),
    ],
)
async def test_enabling_disable_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_forecast_solar: MagicMock,
    key: str,
    name: str,
    value: str,
) -> None:
    """Test the Forecast.Solar sensors that are disabled by default."""
    entry_id = mock_config_entry.entry_id
    entity_id = f"{SENSOR_DOMAIN}.{key}"
    entity_registry = er.async_get(hass)

    # Pre-create registry entry for disabled by default sensor
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{entry_id}_{key}",
        suggested_object_id=key,
        disabled_by=None,
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    entry = entity_registry.async_get(entity_id)
    assert entry
    assert state
    assert entry.unique_id == f"{entry_id}_{key}"
    assert state.state == value
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == name
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == POWER_WATT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_POWER
    assert ATTR_ICON not in state.attributes
