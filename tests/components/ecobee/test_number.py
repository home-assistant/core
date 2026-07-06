"""The test for the ecobee thermostat number module."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform

from tests.common import snapshot_platform

VENTILATOR_MIN_HOME_ID = "number.ecobee_ventilator_minimum_time_home"
VENTILATOR_MIN_AWAY_ID = "number.ecobee_ventilator_minimum_time_away"
COMPRESSOR_MIN_TEMP_ID = "number.ecobee2_compressor_minimum_temperature"
FAN_MIN_ON_TIME_ID = "number.ecobee_fan_minimum_on_time"
THERMOSTAT_ID = 0


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all number entities."""
    config_entry = await setup_platform(hass, NUMBER_DOMAIN)
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_set_min_time_home(hass: HomeAssistant) -> None:
    """Test the number can set min time home."""
    target_value = 40
    with patch(
        "homeassistant.components.ecobee.Ecobee.set_ventilator_min_on_time_home"
    ) as mock_set_min_home_time:
        await setup_platform(hass, NUMBER_DOMAIN)

        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: VENTILATOR_MIN_HOME_ID, ATTR_VALUE: target_value},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_min_home_time.assert_called_once_with(THERMOSTAT_ID, target_value)


async def test_set_min_time_away(hass: HomeAssistant) -> None:
    """Test the number can set min time away."""
    target_value = 0
    with patch(
        "homeassistant.components.ecobee.Ecobee.set_ventilator_min_on_time_away"
    ) as mock_set_min_away_time:
        await setup_platform(hass, NUMBER_DOMAIN)

        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: VENTILATOR_MIN_AWAY_ID, ATTR_VALUE: target_value},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_min_away_time.assert_called_once_with(THERMOSTAT_ID, target_value)


async def test_set_compressor_protection_min_temp(hass: HomeAssistant) -> None:
    """Test the number can set minimum compressor operating temp.

    Ecobee runs in Fahrenheit; the test rig runs in Celsius. Conversions are necessary
    """
    target_value = 0
    with patch(
        "homeassistant.components.ecobee.Ecobee.set_aux_cutover_threshold"
    ) as mock_set_compressor_min_temp:
        await setup_platform(hass, NUMBER_DOMAIN)

        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: COMPRESSOR_MIN_TEMP_ID, ATTR_VALUE: target_value},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_compressor_min_temp.assert_called_once_with(1, 32)


async def test_set_fan_min_on_time(hass: HomeAssistant) -> None:
    """Test the number can set fan minimum on time."""
    target_value = 25
    with patch(
        "homeassistant.components.ecobee.Ecobee.set_fan_min_on_time"
    ) as mock_set_fan_min_on_time:
        await setup_platform(hass, NUMBER_DOMAIN)

        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: FAN_MIN_ON_TIME_ID, ATTR_VALUE: target_value},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_fan_min_on_time.assert_called_once_with(THERMOSTAT_ID, target_value)
