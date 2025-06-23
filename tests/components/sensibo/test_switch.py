"""The test for the sensibo switch platform."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "load_platforms",
    [[Platform.SWITCH]],
)
async def test_switch(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Sensibo switch."""
    await snapshot_platform(hass, entity_registry, snapshot, load_int.entry_id)


async def test_switch_timer(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo switch timer."""

    state = hass.states.get("switch.hallway_timer")
    assert state.state == STATE_OFF
    assert state.attributes["id"] is None
    assert state.attributes["turn_on"] is None

    mock_client.async_set_timer.return_value = {
        "status": "success",
        "result": {"id": "SzTGE4oZ4D"},
    }

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: state.entity_id,
        },
        blocking=True,
    )

    mock_client.async_get_devices_data.return_value.parsed["ABC999111"].timer_on = True
    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].timer_id = "SzTGE4oZ4D"
    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].timer_state_on = False

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("switch.hallway_timer")
    assert state.state == STATE_ON
    assert state.attributes["id"] == "SzTGE4oZ4D"
    assert state.attributes["turn_on"] is False

    mock_client.async_del_timer.return_value = {
        "status": "success",
        "result": {"id": "SzTGE4oZ4D"},
    }

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: state.entity_id,
        },
        blocking=True,
    )

    mock_client.async_get_devices_data.return_value.parsed["ABC999111"].timer_on = False

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("switch.hallway_timer")
    assert state.state == STATE_OFF


async def test_switch_pure_boost(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo switch pure boost."""

    state = hass.states.get("switch.kitchen_pure_boost")
    assert state.state == STATE_OFF

    mock_client.async_set_pureboost.return_value = {"status": "success"}

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: state.entity_id,
        },
        blocking=True,
    )

    mock_client.async_get_devices_data.return_value.parsed[
        "AAZZAAZZ"
    ].pure_boost_enabled = True
    mock_client.async_get_devices_data.return_value.parsed[
        "AAZZAAZZ"
    ].pure_measure_integration = None

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("switch.kitchen_pure_boost")
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: state.entity_id,
        },
        blocking=True,
    )

    mock_client.async_get_devices_data.return_value.parsed[
        "AAZZAAZZ"
    ].pure_boost_enabled = False

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("switch.kitchen_pure_boost")
    assert state.state == STATE_OFF


async def test_switch_command_failure(
    hass: HomeAssistant, load_int: ConfigEntry, mock_client: MagicMock
) -> None:
    """Test the Sensibo switch fails commands."""

    state = hass.states.get("switch.hallway_timer")

    mock_client.async_set_timer.return_value = {"status": "failure"}

    with pytest.raises(
        HomeAssistantError,
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: state.entity_id,
            },
            blocking=True,
        )

    mock_client.async_del_timer.return_value = {"status": "failure"}

    with pytest.raises(
        HomeAssistantError,
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {
                ATTR_ENTITY_ID: state.entity_id,
            },
            blocking=True,
        )


async def test_switch_climate_react(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo switch for climate react."""

    state = hass.states.get("switch.hallway_climate_react")
    assert state.state == STATE_OFF

    mock_client.async_enable_climate_react.return_value = {"status": "success"}

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: state.entity_id,
        },
        blocking=True,
    )

    mock_client.async_get_devices_data.return_value.parsed["ABC999111"].smart_on = True

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("switch.hallway_climate_react")
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: state.entity_id,
        },
        blocking=True,
    )

    mock_client.async_get_devices_data.return_value.parsed["ABC999111"].smart_on = False

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("switch.hallway_climate_react")
    assert state.state == STATE_OFF


async def test_switch_climate_react_no_data(
    hass: HomeAssistant,
    load_int: ConfigEntry,
    mock_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Sensibo switch for climate react with no data."""

    mock_client.async_get_devices_data.return_value.parsed[
        "ABC999111"
    ].smart_type = None

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("switch.hallway_climate_react")
    assert state.state == STATE_OFF

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: state.entity_id,
            },
            blocking=True,
        )
