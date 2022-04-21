"""Test the binary sensors."""
from typing import Any
from unittest.mock import Mock

import pytest

from homeassistant.components.moonraker.connector import generate_signal
from homeassistant.components.moonraker.const import (
    SIGNAL_UPDATE_EXTRUDER,
    SIGNAL_UPDATE_HEAT_BED,
    SIGNAL_UPDATE_PRINT_STATUS,
    SIGNAL_UPDATE_VIRTUAL_SDCARD,
)
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN

from tests.common import MockConfigEntry

HOST_NAME = "test_host"


async def setup_component(
    hass: HomeAssistant, entity_name: str
) -> tuple[str, ConfigEntry]:
    """Set up sensor component."""
    entity_id = f"{SENSOR}.{entity_name}"
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=entity_name,
        title=entity_name,
        data={
            CONF_HOST: f"{HOST_NAME}.local",
            CONF_PORT: 7125,
            CONF_SSL: False,
            CONF_API_KEY: "",
        },
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return entity_id, config_entry


@pytest.mark.parametrize(
    "name,signal,key,value,result",
    [
        ("extruder_temperature", SIGNAL_UPDATE_EXTRUDER, "temperature", 26.97, "27.0"),
        (
            "extruder_target_temperature",
            SIGNAL_UPDATE_EXTRUDER,
            "target",
            210.00,
            "210.0",
        ),
        ("bed_temperature", SIGNAL_UPDATE_HEAT_BED, "temperature", 26.97, "27.0"),
        ("bed_target_temperature", SIGNAL_UPDATE_HEAT_BED, "target", 210.00, "210.0"),
        ("print_progress", SIGNAL_UPDATE_VIRTUAL_SDCARD, "progress", 0.0123, "1"),
        (
            "print_duration",
            SIGNAL_UPDATE_PRINT_STATUS,
            "print_duration",
            (60 * 60) + 60 + 1,  # 1h, 1m, 1s
            "1:01:01",
        ),
        (
            "print_file",
            SIGNAL_UPDATE_PRINT_STATUS,
            "filename",
            "testfile.gcode",
            "testfile.gcode",
        ),
    ],
)
async def test_extruder_temperature(
    hass: HomeAssistant,
    mock_connector: Mock,
    name: str,
    signal: str,
    key: str,
    value: Any,
    result: Any,
) -> None:
    """Test the extruder temperature sensor."""
    entity_id, entry = await setup_component(hass, f"{HOST_NAME}")
    state = hass.states.get(f"{entity_id}_{name}")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    entry_signal = generate_signal(signal, entry.entry_id)
    async_dispatcher_send(hass, entry_signal, {key: value})
    await hass.async_block_till_done()
    state = hass.states.get(f"{entity_id}_{name}")
    assert state.state == result
