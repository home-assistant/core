"""Tests for iAqualink integration."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from iaqualink.client import AqualinkClient
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceUnauthorizedException,
)
from iaqualink.systems.iaqua.device import (
    IaquaAuxSwitch,
    IaquaBinarySensor,
    IaquaLightSwitch,
    IaquaSensor,
    IaquaThermostat,
)
from iaqualink.systems.iaqua.system import IaquaSystem

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.iaqualink.const import UPDATE_INTERVAL
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .conftest import get_aqualink_device, get_aqualink_system

from tests.common import MockConfigEntry, async_fire_time_changed


async def _advance_coordinator_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Advance time to trigger coordinator update interval."""
    freezer.tick(delta=UPDATE_INTERVAL)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_system_refresh_failure_marks_entities_unavailable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a system refresh failure marks attached entities unavailable."""
    config_entry.add_to_hass(hass)

    system = get_aqualink_system(client, cls=IaquaSystem)
    system.online = True
    system.update = AsyncMock()
    systems = {system.serial: system}
    light = get_aqualink_device(
        system, name="aux_1", cls=IaquaLightSwitch, data={"state": "1"}
    )
    devices = {light.name: light}
    system.get_devices = AsyncMock(return_value=devices)

    with (
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.login",
            return_value=None,
        ),
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.get_systems",
            return_value=systems,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    name = f"{LIGHT_DOMAIN}.{light.name}"
    state = hass.states.get(name)
    assert state is not None
    assert state.state == STATE_ON

    async def fail_update() -> None:
        system.online = None
        raise AqualinkServiceException

    system.update = AsyncMock(side_effect=fail_update)

    await _advance_coordinator_time(hass, freezer)

    state = hass.states.get(name)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_light_service_calls_update_entity_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
) -> None:
    """Test light service calls update entity state from device properties."""
    config_entry.add_to_hass(hass)

    system = get_aqualink_system(client, cls=IaquaSystem)
    system.online = True
    system.update = AsyncMock()
    systems = {system.serial: system}
    light = get_aqualink_device(
        system, name="aux_1", cls=IaquaLightSwitch, data={"state": "1"}
    )
    devices = {light.name: light}
    system.get_devices = AsyncMock(return_value=devices)

    async def turn_off() -> None:
        light.data["state"] = "0"

    async def turn_on() -> None:
        light.data["state"] = "1"

    light.turn_off = AsyncMock(side_effect=turn_off)
    light.turn_on = AsyncMock(side_effect=turn_on)

    with (
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.login",
            return_value=None,
        ),
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.get_systems",
            return_value=systems,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = f"{LIGHT_DOMAIN}.{light.name}"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON


async def test_setup_login_exception(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test setup encountering a login exception."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.iaqualink.AqualinkClient.login",
        side_effect=AqualinkServiceException,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_login_unauthorized(hass: HomeAssistant, config_entry) -> None:
    """Test setup encountering an unauthorized exception during login."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.iaqualink.AqualinkClient.login",
        side_effect=AqualinkServiceUnauthorizedException,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_login_timeout(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test setup encountering a timeout while logging in."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.iaqualink.AqualinkClient.login",
        side_effect=TimeoutError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_systems_exception(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test setup encountering an exception while retrieving systems."""
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.login",
            return_value=None,
        ),
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.get_systems",
            side_effect=AqualinkServiceException,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_no_systems_recognized(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test setup ending in no systems recognized."""
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.login",
            return_value=None,
        ),
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.get_systems",
            return_value={},
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_devices_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
) -> None:
    """Test setup encountering an exception while retrieving devices."""
    config_entry.add_to_hass(hass)

    system = get_aqualink_system(client, cls=IaquaSystem)
    system.update = AsyncMock()
    systems = {system.serial: system}

    with (
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.login",
            return_value=None,
        ),
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.get_systems",
            return_value=systems,
        ),
        patch.object(
            system,
            "get_devices",
        ) as mock_get_devices,
    ):
        mock_get_devices.side_effect = AqualinkServiceException
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_all_good_no_recognized_devices(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
) -> None:
    """Test setup ending in no devices recognized."""
    config_entry.add_to_hass(hass)

    system = get_aqualink_system(client, cls=IaquaSystem)
    system.online = True
    system.update = AsyncMock()
    systems = {system.serial: system}

    device = get_aqualink_device(system, name="dev_1")
    devices = {device.name: device}

    with (
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.login",
            return_value=None,
        ),
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.get_systems",
            return_value=systems,
        ),
        patch.object(
            system,
            "get_devices",
        ) as mock_get_devices,
    ):
        mock_get_devices.return_value = devices
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert len(hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)) == 0
    assert len(hass.states.async_entity_ids(CLIMATE_DOMAIN)) == 0
    assert len(hass.states.async_entity_ids(LIGHT_DOMAIN)) == 0
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 0
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_all_good_all_device_types(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
) -> None:
    """Test setup ending in one device of each type recognized."""
    config_entry.add_to_hass(hass)

    system = get_aqualink_system(client, cls=IaquaSystem)
    system.online = True
    system.update = AsyncMock()
    systems = {system.serial: system}

    devices = [
        get_aqualink_device(
            system, name="aux_1", cls=IaquaAuxSwitch, data={"state": "0"}
        ),
        get_aqualink_device(
            system, name="freeze_protection", cls=IaquaBinarySensor, data={"state": "0"}
        ),
        get_aqualink_device(
            system, name="aux_2", cls=IaquaLightSwitch, data={"state": "0"}
        ),
        get_aqualink_device(system, name="ph", cls=IaquaSensor, data={"state": "7.2"}),
        get_aqualink_device(
            system, name="pool_set_point", cls=IaquaThermostat, data={"state": "0"}
        ),
    ]
    devices = {d.name: d for d in devices}

    pool_heater = get_aqualink_device(
        system, name="pool_heater", cls=IaquaAuxSwitch, data={"state": "0"}
    )
    pool_temp = get_aqualink_device(
        system, name="pool_temp", cls=IaquaSensor, data={"state": "72"}
    )
    system.devices = {
        **{d.name: d for d in devices.values()},
        pool_heater.name: pool_heater,
        pool_temp.name: pool_temp,
    }

    system.get_devices = AsyncMock(return_value=devices)

    with (
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.login",
            return_value=None,
        ),
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.get_systems",
            return_value=systems,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert len(hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)) == 1
    assert len(hass.states.async_entity_ids(CLIMATE_DOMAIN)) == 1
    assert len(hass.states.async_entity_ids(LIGHT_DOMAIN)) == 1
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 1
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_multiple_updates(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test all possible results of online status transition after update."""
    config_entry.add_to_hass(hass)

    system = get_aqualink_system(client, cls=IaquaSystem)
    system.online = True
    system.update = AsyncMock()
    systems = {system.serial: system}

    light = get_aqualink_device(
        system, name="aux_1", cls=IaquaLightSwitch, data={"state": "1"}
    )
    devices = {light.name: light}

    system.get_devices = AsyncMock(return_value=devices)

    with (
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.login",
            return_value=None,
        ),
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.get_systems",
            return_value=systems,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{LIGHT_DOMAIN}.{light.name}"

    def assert_state(expected_state: str) -> None:
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == expected_state

    def set_online_to_true():
        system.online = True

    def set_online_to_false():
        system.online = False

    async def fail_update() -> None:
        system.online = None
        raise AqualinkServiceException

    system.update = AsyncMock()

    # True -> True
    system.online = True
    system.update.side_effect = set_online_to_true
    await _advance_coordinator_time(hass, freezer)
    assert system.update.await_count == 1
    assert_state(STATE_ON)

    # True -> False
    system.online = True
    system.update.side_effect = set_online_to_false
    await _advance_coordinator_time(hass, freezer)
    assert system.update.await_count == 2
    assert_state(STATE_UNAVAILABLE)

    # True -> None / ServiceException
    system.online = True
    system.update.side_effect = fail_update
    await _advance_coordinator_time(hass, freezer)
    assert system.update.await_count == 3
    assert_state(STATE_UNAVAILABLE)

    # False -> False
    system.online = False
    system.update.side_effect = set_online_to_false
    await _advance_coordinator_time(hass, freezer)
    assert system.update.await_count == 4
    assert_state(STATE_UNAVAILABLE)

    # False -> True
    system.online = False
    system.update.side_effect = set_online_to_true
    await _advance_coordinator_time(hass, freezer)
    assert system.update.await_count == 5
    assert_state(STATE_ON)

    # False -> None / ServiceException
    system.online = False
    system.update.side_effect = fail_update
    await _advance_coordinator_time(hass, freezer)
    assert system.update.await_count == 6
    assert_state(STATE_UNAVAILABLE)

    # None -> None / ServiceException
    system.online = None
    system.update.side_effect = fail_update
    await _advance_coordinator_time(hass, freezer)
    assert system.update.await_count == 7
    assert_state(STATE_UNAVAILABLE)

    # None -> True
    system.online = None
    system.update.side_effect = set_online_to_true
    await _advance_coordinator_time(hass, freezer)
    assert system.update.await_count == 8
    assert_state(STATE_ON)

    # None -> False
    system.online = None
    system.update.side_effect = set_online_to_false
    await _advance_coordinator_time(hass, freezer)
    assert system.update.await_count == 9
    assert_state(STATE_UNAVAILABLE)

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_entity_assumed_and_available(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test assumed_state and_available properties for all values of online."""
    config_entry.add_to_hass(hass)

    system = get_aqualink_system(client, cls=IaquaSystem)
    system.online = True
    systems = {system.serial: system}

    light = get_aqualink_device(
        system, name="aux_1", cls=IaquaLightSwitch, data={"state": "1"}
    )
    devices = {light.name: light}
    system.get_devices = AsyncMock(return_value=devices)
    system.update = AsyncMock()

    with (
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.login",
            return_value=None,
        ),
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.get_systems",
            return_value=systems,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(LIGHT_DOMAIN)) == 1

    name = f"{LIGHT_DOMAIN}.{light.name}"

    # None means maybe.
    light.system.online = None
    await _advance_coordinator_time(hass, freezer)
    state = hass.states.get(name)
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes.get(ATTR_ASSUMED_STATE) is True

    light.system.online = False
    await _advance_coordinator_time(hass, freezer)
    state = hass.states.get(name)
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes.get(ATTR_ASSUMED_STATE) is True

    light.system.online = True
    await _advance_coordinator_time(hass, freezer)
    state = hass.states.get(name)
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE) is None
