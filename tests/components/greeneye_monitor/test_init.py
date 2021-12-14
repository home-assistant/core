"""Tests for greeneye_monitor component initialization."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.greeneye_monitor import (
    CONF_MONITORS,
    CONF_NUMBER,
    CONF_SERIAL_NUMBER,
    CONF_TEMPERATURE_SENSORS,
    DOMAIN,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_PORT,
    CONF_SENSORS,
    CONF_TEMPERATURE_UNIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import (
    SINGLE_MONITOR_CONFIG_NO_SENSORS,
    SINGLE_MONITOR_CONFIG_POWER_SENSORS,
    SINGLE_MONITOR_CONFIG_PULSE_COUNTERS,
    SINGLE_MONITOR_CONFIG_TEMPERATURE_SENSORS,
    SINGLE_MONITOR_CONFIG_VOLTAGE_SENSORS,
    SINGLE_MONITOR_SERIAL_NUMBER,
    setup_greeneye_monitor_component_with_config,
)
from .conftest import (
    assert_power_sensor_registered,
    assert_pulse_counter_registered,
    assert_temperature_sensor_registered,
    assert_voltage_sensor_registered,
)


async def test_setup_fails_if_no_sensors_defined(
    hass: HomeAssistant, monitors: AsyncMock
) -> None:
    """Test that component setup fails if there are no sensors defined in the YAML."""
    success = await setup_greeneye_monitor_component_with_config(
        hass, SINGLE_MONITOR_CONFIG_NO_SENSORS
    )
    assert not success


@pytest.mark.xfail(reason="Currently failing. Will fix in subsequent PR.")
async def test_setup_succeeds_no_config(
    hass: HomeAssistant, monitors: AsyncMock
) -> None:
    """Test that component setup succeeds if there is no config present in the YAML."""
    assert await async_setup_component(hass, DOMAIN, {})


async def test_setup_creates_temperature_entities(
    hass: HomeAssistant, monitors: AsyncMock
) -> None:
    """Test that component setup registers temperature sensors properly."""
    assert await setup_greeneye_monitor_component_with_config(
        hass, SINGLE_MONITOR_CONFIG_TEMPERATURE_SENSORS
    )

    assert_temperature_sensor_registered(
        hass, SINGLE_MONITOR_SERIAL_NUMBER, 1, "temp_a"
    )
    assert_temperature_sensor_registered(
        hass, SINGLE_MONITOR_SERIAL_NUMBER, 2, "temp_2"
    )
    assert_temperature_sensor_registered(
        hass, SINGLE_MONITOR_SERIAL_NUMBER, 3, "temp_c"
    )
    assert_temperature_sensor_registered(
        hass, SINGLE_MONITOR_SERIAL_NUMBER, 4, "temp_d"
    )
    assert_temperature_sensor_registered(
        hass, SINGLE_MONITOR_SERIAL_NUMBER, 5, "temp_5"
    )
    assert_temperature_sensor_registered(
        hass, SINGLE_MONITOR_SERIAL_NUMBER, 6, "temp_f"
    )
    assert_temperature_sensor_registered(
        hass, SINGLE_MONITOR_SERIAL_NUMBER, 7, "temp_g"
    )
    assert_temperature_sensor_registered(
        hass, SINGLE_MONITOR_SERIAL_NUMBER, 8, "temp_h"
    )


async def test_setup_creates_pulse_counter_entities(
    hass: HomeAssistant, monitors: AsyncMock
) -> None:
    """Test that component setup registers pulse counters properly."""
    assert await setup_greeneye_monitor_component_with_config(
        hass, SINGLE_MONITOR_CONFIG_PULSE_COUNTERS
    )

    assert_pulse_counter_registered(
        hass,
        SINGLE_MONITOR_SERIAL_NUMBER,
        1,
        "pulse_a",
        "pulses",
        "s",
    )
    assert_pulse_counter_registered(
        hass, SINGLE_MONITOR_SERIAL_NUMBER, 2, "pulse_2", "gal", "min"
    )
    assert_pulse_counter_registered(
        hass,
        SINGLE_MONITOR_SERIAL_NUMBER,
        3,
        "pulse_3",
        "gal",
        "h",
    )
    assert_pulse_counter_registered(
        hass,
        SINGLE_MONITOR_SERIAL_NUMBER,
        4,
        "pulse_d",
        "pulses",
        "s",
    )


async def test_setup_creates_power_sensor_entities(
    hass: HomeAssistant, monitors: AsyncMock
) -> None:
    """Test that component setup registers power sensors correctly."""
    assert await setup_greeneye_monitor_component_with_config(
        hass, SINGLE_MONITOR_CONFIG_POWER_SENSORS
    )

    assert_power_sensor_registered(hass, SINGLE_MONITOR_SERIAL_NUMBER, 1, "channel 1")
    assert_power_sensor_registered(hass, SINGLE_MONITOR_SERIAL_NUMBER, 2, "channel two")


async def test_setup_creates_voltage_sensor_entities(
    hass: HomeAssistant, monitors: AsyncMock
) -> None:
    """Test that component setup registers voltage sensors properly."""
    assert await setup_greeneye_monitor_component_with_config(
        hass, SINGLE_MONITOR_CONFIG_VOLTAGE_SENSORS
    )

    assert_voltage_sensor_registered(hass, SINGLE_MONITOR_SERIAL_NUMBER, 1, "voltage 1")


async def test_multi_monitor_config(hass: HomeAssistant, monitors: AsyncMock) -> None:
    """Test that component setup registers entities from multiple monitors correctly."""
    assert await setup_greeneye_monitor_component_with_config(
        hass,
        {
            DOMAIN: {
                CONF_PORT: 7513,
                CONF_MONITORS: [
                    {
                        CONF_SERIAL_NUMBER: "00000001",
                        CONF_TEMPERATURE_SENSORS: {
                            CONF_TEMPERATURE_UNIT: "C",
                            CONF_SENSORS: [
                                {CONF_NUMBER: 1, CONF_NAME: "unit_1_temp_1"}
                            ],
                        },
                    },
                    {
                        CONF_SERIAL_NUMBER: "00000002",
                        CONF_TEMPERATURE_SENSORS: {
                            CONF_TEMPERATURE_UNIT: "F",
                            CONF_SENSORS: [
                                {CONF_NUMBER: 1, CONF_NAME: "unit_2_temp_1"}
                            ],
                        },
                    },
                ],
            }
        },
    )

    assert_temperature_sensor_registered(hass, 1, 1, "unit_1_temp_1")
    assert_temperature_sensor_registered(hass, 2, 1, "unit_2_temp_1")


async def test_setup_and_shutdown(hass: HomeAssistant, monitors: AsyncMock) -> None:
    """Test that the component can set up and shut down cleanly, closing the underlying server on shutdown."""
    server = AsyncMock()
    monitors.start_server = AsyncMock(return_value=server)
    assert await setup_greeneye_monitor_component_with_config(
        hass, SINGLE_MONITOR_CONFIG_POWER_SENSORS
    )

    await hass.async_stop()

    assert server.close.called
