"""The test for the sensibo number platform."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from pysensibo.model import SensiboData
import pytest
from pytest import MonkeyPatch

from homeassistant.components.number.const import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt

from tests.common import async_fire_time_changed


async def test_number(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: AsyncMock,
    load_int: ConfigEntry,
    monkeypatch: MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo number."""

    state1 = hass.states.get("number.hallway_temperature_calibration")
    state2 = hass.states.get("number.hallway_humidity_calibration")
    assert state1.state == "0.1"
    assert state2.state == "0.0"

    monkeypatch.setattr(get_data.parsed["ABC999111"], "calibration_temp", 0.2)

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get("number.hallway_temperature_calibration")
    assert state1.state == "0.2"


async def test_number_set_value(
    hass: HomeAssistant,
    entity_registry_enabled_by_default: AsyncMock,
    load_int: ConfigEntry,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo number service."""

    state1 = hass.states.get("number.hallway_temperature_calibration")
    assert state1.state == "0.1"

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_calibration",
        return_value={"status": "failure"},
    ):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                NUMBER_DOMAIN,
                SERVICE_SET_VALUE,
                {ATTR_ENTITY_ID: state1.entity_id, ATTR_VALUE: "0.2"},
                blocking=True,
            )
        await hass.async_block_till_done()

    state2 = hass.states.get("number.hallway_temperature_calibration")
    assert state2.state == "0.1"

    with patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ), patch(
        "homeassistant.components.sensibo.util.SensiboClient.async_set_calibration",
        return_value={"status": "success"},
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: state1.entity_id, ATTR_VALUE: "0.2"},
            blocking=True,
        )
    await hass.async_block_till_done()

    state2 = hass.states.get("number.hallway_temperature_calibration")
    assert state2.state == "0.2"
