"""The test for the sensibo switch platform."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from pysensibo.model import SensiboData
import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed


async def test_switch_timer(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo switch."""

    state1 = hass.states.get("switch.hallway_timer")
    assert state1.state == STATE_OFF
    assert state1.attributes["id"] is None
    assert state1.attributes["turn_on"] is None

    with (
        patch(
            "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
            return_value=get_data,
        ),
        patch(
            "homeassistant.components.sensibo.util.SensiboClient.async_set_timer",
            return_value={"status": "success", "result": {"id": "SzTGE4oZ4D"}},
        ),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: state1.entity_id,
            },
            blocking=True,
        )
    await hass.async_block_till_done()

    monkeypatch.setattr(get_data.parsed["ABC999111"], "timer_on", True)
    monkeypatch.setattr(get_data.parsed["ABC999111"], "timer_id", "SzTGE4oZ4D")
    monkeypatch.setattr(get_data.parsed["ABC999111"], "timer_state_on", False)
    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()
    state1 = hass.states.get("switch.hallway_timer")
    assert state1.state == STATE_ON
    assert state1.attributes["id"] == "SzTGE4oZ4D"
    assert state1.attributes["turn_on"] is False

    with (
        patch(
            "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
            return_value=get_data,
        ),
        patch(
            "homeassistant.components.sensibo.util.SensiboClient.async_del_timer",
            return_value={"status": "success", "result": {"id": "SzTGE4oZ4D"}},
        ),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {
                ATTR_ENTITY_ID: state1.entity_id,
            },
            blocking=True,
        )
    await hass.async_block_till_done()

    monkeypatch.setattr(get_data.parsed["ABC999111"], "timer_on", False)

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get("switch.hallway_timer")
    assert state1.state == STATE_OFF


async def test_switch_pure_boost(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo switch."""

    state1 = hass.states.get("switch.kitchen_pure_boost")
    assert state1.state == STATE_OFF

    with (
        patch(
            "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
            return_value=get_data,
        ),
        patch(
            "homeassistant.components.sensibo.util.SensiboClient.async_set_pureboost",
            return_value={"status": "success"},
        ),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: state1.entity_id,
            },
            blocking=True,
        )
    await hass.async_block_till_done()

    monkeypatch.setattr(get_data.parsed["AAZZAAZZ"], "pure_boost_enabled", True)
    monkeypatch.setattr(get_data.parsed["AAZZAAZZ"], "pure_measure_integration", None)

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()
    state1 = hass.states.get("switch.kitchen_pure_boost")
    assert state1.state == STATE_ON

    with (
        patch(
            "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
            return_value=get_data,
        ),
        patch(
            "homeassistant.components.sensibo.util.SensiboClient.async_set_pureboost",
            return_value={"status": "success"},
        ),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {
                ATTR_ENTITY_ID: state1.entity_id,
            },
            blocking=True,
        )
    await hass.async_block_till_done()

    monkeypatch.setattr(get_data.parsed["AAZZAAZZ"], "pure_boost_enabled", False)

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get("switch.kitchen_pure_boost")
    assert state1.state == STATE_OFF


async def test_switch_command_failure(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo switch fails commands."""

    state1 = hass.states.get("switch.hallway_timer")

    with (
        patch(
            "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
            return_value=get_data,
        ),
        patch(
            "homeassistant.components.sensibo.util.SensiboClient.async_set_timer",
            return_value={"status": "failure"},
        ),
        pytest.raises(
            HomeAssistantError,
        ),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: state1.entity_id,
            },
            blocking=True,
        )

    with (
        patch(
            "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
            return_value=get_data,
        ),
        patch(
            "homeassistant.components.sensibo.util.SensiboClient.async_del_timer",
            return_value={"status": "failure"},
        ),
        pytest.raises(
            HomeAssistantError,
        ),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {
                ATTR_ENTITY_ID: state1.entity_id,
            },
            blocking=True,
        )


async def test_switch_climate_react(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo switch for climate react."""

    state1 = hass.states.get("switch.hallway_climate_react")
    assert state1.state == STATE_OFF

    with (
        patch(
            "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
            return_value=get_data,
        ),
        patch(
            "homeassistant.components.sensibo.util.SensiboClient.async_enable_climate_react",
            return_value={"status": "success"},
        ),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: state1.entity_id,
            },
            blocking=True,
        )
    await hass.async_block_till_done()

    monkeypatch.setattr(get_data.parsed["ABC999111"], "smart_on", True)

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()
    state1 = hass.states.get("switch.hallway_climate_react")
    assert state1.state == STATE_ON

    with (
        patch(
            "homeassistant.components.sensibo.util.SensiboClient.async_get_devices_data",
            return_value=get_data,
        ),
        patch(
            "homeassistant.components.sensibo.util.SensiboClient.async_enable_climate_react",
            return_value={"status": "success"},
        ),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {
                ATTR_ENTITY_ID: state1.entity_id,
            },
            blocking=True,
        )
    await hass.async_block_till_done()

    monkeypatch.setattr(get_data.parsed["ABC999111"], "smart_on", False)

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get("switch.hallway_climate_react")
    assert state1.state == STATE_OFF


async def test_switch_climate_react_no_data(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    get_data: SensiboData,
) -> None:
    """Test the Sensibo switch for climate react."""

    monkeypatch.setattr(get_data.parsed["ABC999111"], "smart_type", None)

    with patch(
        "homeassistant.components.sensibo.coordinator.SensiboClient.async_get_devices_data",
        return_value=get_data,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(minutes=5),
        )
        await hass.async_block_till_done()

    state1 = hass.states.get("switch.hallway_climate_react")
    assert state1.state == STATE_OFF

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: state1.entity_id,
            },
            blocking=True,
        )
    await hass.async_block_till_done()
