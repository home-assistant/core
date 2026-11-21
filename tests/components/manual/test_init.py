"""Test setting up the manual alarm control panel from a config entry."""

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_DOMAIN,
    AlarmControlPanelState,
)
from homeassistant.components.manual.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

ENTITY_ID = "alarm_control_panel.my_alarm"
CODE = "1234"

OPTIONS: dict[str, Any] = {
    "name": "My alarm",
    "code": CODE,
    "code_arm_required": True,
    "arming_states": ["armed_away", "armed_home"],
    "arming_time": {"seconds": 10},
    "delay_time": {"seconds": 5},
    "trigger_time": {"seconds": 30},
    "disarm_after_trigger": True,
}


@pytest.fixture
async def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up a manual alarm config entry."""
    entry = MockConfigEntry(domain=DOMAIN, options=OPTIONS, title="My alarm")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_and_unload(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test the entity is created from the entry and removed on unload."""
    entity = entity_registry.async_get(ENTITY_ID)
    assert entity is not None
    assert entity.unique_id == config_entry.entry_id
    assert entity.config_entry_id == config_entry.entry_id

    state = hass.states.get(ENTITY_ID)
    assert state.state == AlarmControlPanelState.DISARMED
    assert state.attributes["code_format"] == "number"
    assert state.attributes["code_arm_required"] is True

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get(ENTITY_ID).state == "unavailable"


async def test_arm_without_code(hass: HomeAssistant) -> None:
    """Test an entry without a code can be armed without a code."""
    options = {key: value for key, value in OPTIONS.items() if key != "code"}
    entry = MockConfigEntry(domain=DOMAIN, options=options, title="My alarm")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.attributes["code_format"] is None
    assert state.attributes["code_arm_required"] is False

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_ARM_AWAY,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).state == AlarmControlPanelState.ARMING


async def test_code_template_and_state_overrides(hass: HomeAssistant) -> None:
    """Test the code template and per-state timing overrides are used."""
    options = {key: value for key, value in OPTIONS.items() if key != "code"}
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            **options,
            "code_template": "{{ '4321' if to_state == 'armed_away' else '1234' }}",
            "armed_away": {"arming_time": {"seconds": 0}},
        },
        title="My alarm",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).attributes["code_format"] == "text"

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            ALARM_DOMAIN,
            SERVICE_ALARM_ARM_AWAY,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_CODE: CODE},
            blocking=True,
        )

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_ARM_AWAY,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_CODE: "4321"},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).state == AlarmControlPanelState.ARMED_AWAY

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_ARM_HOME,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_CODE: CODE},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).state == AlarmControlPanelState.ARMING


@pytest.mark.usefixtures("config_entry")
async def test_invalid_code(hass: HomeAssistant) -> None:
    """Test arming with an invalid code is rejected."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            ALARM_DOMAIN,
            SERVICE_ALARM_ARM_AWAY,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_CODE: "0000"},
            blocking=True,
        )
    assert hass.states.get(ENTITY_ID).state == AlarmControlPanelState.DISARMED


@pytest.mark.usefixtures("config_entry")
async def test_configured_timings(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the configured arming, delay and trigger times are used."""
    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_ARM_AWAY,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_CODE: CODE},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).state == AlarmControlPanelState.ARMING

    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == AlarmControlPanelState.ARMED_AWAY

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_TRIGGER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).state == AlarmControlPanelState.PENDING

    freezer.tick(timedelta(seconds=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == AlarmControlPanelState.TRIGGERED

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == AlarmControlPanelState.DISARMED

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_DISARM,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_CODE: CODE},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).state == AlarmControlPanelState.DISARMED


async def test_reload_after_arming_completed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
) -> None:
    """Test a reload after arming completed keeps the alarm armed."""
    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_ARM_AWAY,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_CODE: CODE},
        blocking=True,
    )
    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == AlarmControlPanelState.ARMED_AWAY

    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == AlarmControlPanelState.ARMED_AWAY


async def test_reload_after_pending_completed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
) -> None:
    """Test a reload after pending ended keeps the original trigger timing."""
    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_ARM_AWAY,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_CODE: CODE},
        blocking=True,
    )
    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    await hass.services.async_call(
        ALARM_DOMAIN,
        SERVICE_ALARM_TRIGGER,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    freezer.tick(timedelta(seconds=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == AlarmControlPanelState.TRIGGERED

    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == AlarmControlPanelState.TRIGGERED

    # Trigger time ends 35 seconds after the trigger, 29 seconds from now
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == AlarmControlPanelState.DISARMED
