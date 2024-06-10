"""The test for the sensibo select platform."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from pysensibo.model import SensiboData
import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed


async def test_select(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo select."""

    state1 = hass.states.get("select.hallway_horizontal_swing")
    assert state1.state == "stopped"

    monkeypatch.setattr(
        get_data.parsed["ABC999111"], "horizontal_swing_mode", "fixedleft"
    )

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get("select.hallway_horizontal_swing")
    assert state1.state == "fixedleft"


async def test_select_set_option(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo select service."""

    monkeypatch.setattr(
        get_data.parsed["ABC999111"],
        "active_features",
        [
            "timestamp",
            "on",
            "mode",
            "targetTemperature",
            "light",
        ],
    )

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get("select.hallway_horizontal_swing")
    assert state1.state == "stopped"

    with (
        patch(
            "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
            return_value=get_data,
        ),
        patch(
            "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
            return_value={"result": {"status": "failed"}},
        ),
        pytest.raises(
            HomeAssistantError,
        ),
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: state1.entity_id, ATTR_OPTION: "fixedleft"},
            blocking=True,
        )
    await hass.async_block_till_done()

    state2 = hass.states.get("select.hallway_horizontal_swing")
    assert state2.state == "stopped"

    monkeypatch.setattr(
        get_data.parsed["ABC999111"],
        "active_features",
        [
            "timestamp",
            "on",
            "mode",
            "targetTemperature",
            "horizontalSwing",
            "light",
        ],
    )

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    with (
        patch(
            "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
        ),
        patch(
            "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
            return_value={
                "result": {"status": "Failed", "failureReason": "No connection"}
            },
        ),
        pytest.raises(
            HomeAssistantError,
        ),
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: state1.entity_id, ATTR_OPTION: "fixedleft"},
            blocking=True,
        )
    await hass.async_block_till_done()

    state2 = hass.states.get("select.hallway_horizontal_swing")
    assert state2.state == "stopped"

    with (
        patch(
            "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
            return_value=get_data,
        ),
        patch(
            "homeassistant.components.sensibo.util.SensiboClient.async_set_ac_state_property",
            return_value={"result": {"status": "Success"}},
        ),
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: state1.entity_id, ATTR_OPTION: "fixedleft"},
            blocking=True,
        )
    await hass.async_block_till_done()

    state2 = hass.states.get("select.hallway_horizontal_swing")
    assert state2.state == "fixedleft"
