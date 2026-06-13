"""Tests for iAquaLink integration."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import httpx
from iaqualink.client import AqualinkClient
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkServiceUnauthorizedException,
)
from iaqualink.systems.iaqua.device import IaquaAuxSwitch, IaquaLightSwitch
from iaqualink.systems.iaqua.system import IaquaSystem
import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.iaqualink.const import (
    DOMAIN,
    UPDATE_INTERVAL_BY_SYSTEM_TYPE,
)
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
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
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import get_aqualink_device, get_aqualink_system, setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def _advance_coordinator_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Advance time to trigger coordinator update interval."""
    update_interval = UPDATE_INTERVAL_BY_SYSTEM_TYPE["iaqua"]

    freezer.tick(delta=update_interval)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)


def _build_single_light_system(
    client: AqualinkClient,
) -> IaquaSystem:
    """Build a system with a single light device for stale-cleanup tests."""
    system = get_aqualink_system(
        client,
        cls=IaquaSystem,
        data={"home_screen": [{}, {}, {}, {"temp_scale": "F"}]},
    )
    system.online = True

    async def update() -> None:
        system.temp_unit = "F"

    system.update = AsyncMock(side_effect=update)

    light = get_aqualink_device(
        system,
        name="aux_2",
        cls=IaquaLightSwitch,
        data={"state": "1", "aux": "2", "label": "Pool Light"},
    )
    system.devices = {light.name: light}
    system.get_devices = AsyncMock(return_value={light.name: light})
    system.set_aux = AsyncMock()
    system.set_light = AsyncMock()
    return system


async def _setup_system(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    system: IaquaSystem,
) -> None:
    """Set up the integration with patches (config entry must already be added)."""
    with (
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.login",
            return_value=None,
        ),
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.get_systems",
            return_value={system.serial: system},
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.parametrize(
    "raised_exception",
    [
        pytest.param(AqualinkServiceException, id="service"),
        pytest.param(TimeoutError, id="timeout"),
        pytest.param(httpx.HTTPError("boom"), id="http"),
    ],
)
async def test_system_refresh_failure_marks_entities_unavailable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    freezer: FrozenDateTimeFactory,
    raised_exception: Exception | type[Exception],
) -> None:
    """Test a system refresh failure marks attached entities unavailable."""
    devices = await setup_integration(hass, config_entry, client)

    entity_ids = hass.states.async_entity_ids(LIGHT_DOMAIN)
    assert len(entity_ids) == 1
    entity_id = entity_ids[0]

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    async def fail_update() -> None:
        devices.system.online = None
        raise raised_exception

    devices.system.update = AsyncMock(side_effect=fail_update)

    await _advance_coordinator_time(hass, freezer)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_system_rate_limited_keeps_entities_available(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a rate-limited update keeps entities at their last known state."""
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

    entity_ids = hass.states.async_entity_ids(LIGHT_DOMAIN)
    assert len(entity_ids) == 1
    entity_id = entity_ids[0]

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    system.update = AsyncMock(side_effect=AqualinkServiceThrottledException)

    await _advance_coordinator_time(hass, freezer)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON
    assert "Rate limited by iAquaLink" in caplog.text


async def test_light_service_calls_update_entity_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
) -> None:
    """Test light service calls update entity state from device properties."""
    devices = await setup_integration(hass, config_entry, client)

    async def turn_off() -> None:
        devices.light.data["state"] = "0"

    async def turn_on() -> None:
        devices.light.data["state"] = "1"

    devices.light.turn_off = AsyncMock(side_effect=turn_off)
    devices.light.turn_on = AsyncMock(side_effect=turn_on)

    entity_ids = hass.states.async_entity_ids(LIGHT_DOMAIN)
    assert len(entity_ids) == 1
    entity_id = entity_ids[0]

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


@pytest.mark.parametrize(
    "raised_exception",
    [
        pytest.param(AqualinkServiceException, id="service"),
        pytest.param(TimeoutError, id="timeout"),
        pytest.param(httpx.HTTPError("boom"), id="http"),
    ],
)
async def test_setup_login_retry_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    raised_exception: Exception | type[Exception],
) -> None:
    """Test setup retries on connection-related login exceptions."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.iaqualink.AqualinkClient.login",
        side_effect=raised_exception,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_login_unauthorized(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test setup encountering an unauthorized exception during login."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.iaqualink.AqualinkClient.login",
        side_effect=AqualinkServiceUnauthorizedException,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


@pytest.mark.parametrize(
    "raised_exception",
    [
        pytest.param(AqualinkServiceException, id="service"),
        pytest.param(TimeoutError, id="timeout"),
        pytest.param(httpx.HTTPError("boom"), id="http"),
    ],
)
async def test_setup_systems_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    raised_exception: Exception | type[Exception],
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
            side_effect=raised_exception,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_systems_unauthorized(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test setup encountering an unauthorized exception while retrieving systems."""
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.login",
            return_value=None,
        ),
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.get_systems",
            side_effect=AqualinkServiceUnauthorizedException,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


async def test_setup_first_refresh_unauthorized_closes_client(
    hass: HomeAssistant, config_entry: MockConfigEntry, client: AqualinkClient
) -> None:
    """Test setup closes the client when first refresh triggers reauthentication."""
    config_entry.add_to_hass(hass)

    system = get_aqualink_system(client, cls=IaquaSystem)
    system.update = AsyncMock(side_effect=AqualinkServiceUnauthorizedException)
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
        patch(
            "homeassistant.components.iaqualink.AqualinkClient.close",
            new_callable=AsyncMock,
        ) as mock_close,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    mock_close.assert_awaited_once()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


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


@pytest.mark.parametrize(
    "raised_exception",
    [
        pytest.param(AqualinkServiceException, id="service"),
        pytest.param(TimeoutError, id="timeout"),
        pytest.param(httpx.HTTPError("boom"), id="http"),
    ],
)
async def test_setup_devices_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    raised_exception: Exception | type[Exception],
) -> None:
    """Test setup encountering an exception while retrieving devices."""
    config_entry.add_to_hass(hass)

    system = get_aqualink_system(client, cls=IaquaSystem)
    system.online = True
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
        mock_get_devices.side_effect = raised_exception
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_devices_unauthorized(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
) -> None:
    """Test setup encountering an unauthorized exception while retrieving devices."""
    config_entry.add_to_hass(hass)

    system = get_aqualink_system(client, cls=IaquaSystem)
    system.online = True
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
            side_effect=AqualinkServiceUnauthorizedException,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


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
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup ending in one device of each type recognized."""
    await setup_integration(hass, config_entry, client)

    assert config_entry.state is ConfigEntryState.LOADED

    assert len(hass.states.async_entity_ids(BINARY_SENSOR_DOMAIN)) == 1
    assert len(hass.states.async_entity_ids(CLIMATE_DOMAIN)) == 1
    assert len(hass.states.async_entity_ids(LIGHT_DOMAIN)) == 1
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 1
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1

    for domain in (
        BINARY_SENSOR_DOMAIN,
        CLIMATE_DOMAIN,
        LIGHT_DOMAIN,
        SENSOR_DOMAIN,
        SWITCH_DOMAIN,
    ):
        for entity_id in hass.states.async_entity_ids(domain):
            entry = entity_registry.async_get(entity_id)
            assert entry is not None
            assert entry.has_entity_name is True

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
    devices = await setup_integration(hass, config_entry, client)
    system = devices.system

    assert config_entry.state is ConfigEntryState.LOADED

    entity_ids = hass.states.async_entity_ids(LIGHT_DOMAIN)
    assert len(entity_ids) == 1
    entity_id = entity_ids[0]

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
    devices = await setup_integration(hass, config_entry, client)

    entity_ids = hass.states.async_entity_ids(LIGHT_DOMAIN)
    assert len(entity_ids) == 1

    name = entity_ids[0]

    # None means maybe.
    devices.light.system.online = None
    await _advance_coordinator_time(hass, freezer)
    state = hass.states.get(name)
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes.get(ATTR_ASSUMED_STATE) is True

    devices.light.system.online = False
    await _advance_coordinator_time(hass, freezer)
    state = hass.states.get(name)
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes.get(ATTR_ASSUMED_STATE) is True

    devices.light.system.online = True
    await _advance_coordinator_time(hass, freezer)
    state = hass.states.get(name)
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE) is None


async def test_system_refresh_unauthorized_triggers_reauth(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an unauthorized refresh starts reauthentication."""
    devices = await setup_integration(hass, config_entry, client)

    assert config_entry.state is ConfigEntryState.LOADED

    devices.system.update = AsyncMock(side_effect=AqualinkServiceUnauthorizedException)

    await _advance_coordinator_time(hass, freezer)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == config_entry.entry_id


async def test_dynamic_device_addition(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test new devices discovered at runtime are dynamically added."""
    devices = await setup_integration(hass, config_entry, client)

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1
    assert len(hass.states.async_entity_ids(LIGHT_DOMAIN)) == 1

    new_switch = get_aqualink_device(
        devices.system,
        name="aux_3",
        cls=IaquaAuxSwitch,
        data={"state": "1", "aux": "4"},
    )

    original_devices = dict(devices.system.get_devices.return_value)
    updated_devices = {**original_devices, new_switch.name: new_switch}
    devices.system.get_devices = AsyncMock(return_value=updated_devices)

    await _advance_coordinator_time(hass, freezer)

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 2
    state = hass.states.get("switch.aux_3")
    assert state is not None
    assert state.state == STATE_ON


async def test_stale_device_removal(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test devices removed from the system are cleaned up from the registry."""
    devices = await setup_integration(hass, config_entry, client)

    switch_device_id = f"{devices.system.serial}_aux_1"
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, switch_device_id)}
    )
    assert device_entry is not None

    original_devices = dict(devices.system.get_devices.return_value)
    reduced_devices = {k: v for k, v in original_devices.items() if k != "aux_1"}
    devices.system.get_devices = AsyncMock(return_value=reduced_devices)

    await _advance_coordinator_time(hass, freezer)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, switch_device_id)}
    )
    assert device_entry is None


@pytest.mark.parametrize(
    ("orphan_identifiers", "extra_identifiers"),
    [
        pytest.param(
            [("{serial}_removed_device",)],
            [],
            id="previous_session",
        ),
        pytest.param(
            [("OLD_SERIAL",), ("OLD_SERIAL_aux_1",)],
            [("other_domain", "other_id")],
            id="stale_system",
        ),
    ],
)
async def test_stale_device_cleanup_on_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    device_registry: dr.DeviceRegistry,
    orphan_identifiers: list[tuple[str]],
    extra_identifiers: list[tuple[str, str]],
) -> None:
    """Test stale devices are cleaned up on setup."""
    config_entry.add_to_hass(hass)
    system = _build_single_light_system(client)

    # Create orphan devices that should be removed.
    resolved = [ident[0].format(serial=system.serial) for ident in orphan_identifiers]
    for identifier in resolved:
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, identifier)},
            name=f"Orphan {identifier}",
        )
    # Device with only a non-iaqualink identifier (triggers domain != DOMAIN skip).
    for ident in extra_identifiers:
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={ident},
            name="Non-iaqualink Device",
        )

    await _setup_system(hass, config_entry, system)

    assert config_entry.state is ConfigEntryState.LOADED

    # All orphan devices should be gone.
    for identifier in resolved:
        assert (
            device_registry.async_get_device(identifiers={(DOMAIN, identifier)}) is None
        )

    # New system's device should exist.
    assert (
        device_registry.async_get_device(
            identifiers={(DOMAIN, f"{system.serial}_aux_2")}
        )
        is not None
    )


async def test_entity_domain_change_cleanup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entities are removed when a device changes platform domain."""
    config_entry.add_to_hass(hass)
    system = _build_single_light_system(client)

    # Simulate a device that was previously a switch but is now a light.
    # Pre-create an entity registry entry under the switch platform.
    entity_registry.async_get_or_create(
        domain="switch",
        platform=DOMAIN,
        unique_id=f"{system.serial}_aux_2",
        config_entry=config_entry,
    )
    assert entity_registry.async_get_entity_id(
        "switch", DOMAIN, f"{system.serial}_aux_2"
    )

    # Entity with a unique_id not matching any current device (should be kept).
    entity_registry.async_get_or_create(
        domain="switch",
        platform=DOMAIN,
        unique_id=f"{system.serial}_old_removed",
        config_entry=config_entry,
    )

    await _setup_system(hass, config_entry, system)

    assert config_entry.state is ConfigEntryState.LOADED

    # Old switch entity should be gone.
    assert (
        entity_registry.async_get_entity_id("switch", DOMAIN, f"{system.serial}_aux_2")
        is None
    )

    # New light entity should exist.
    assert (
        entity_registry.async_get_entity_id("light", DOMAIN, f"{system.serial}_aux_2")
        is not None
    )

    # Entity with unmatched unique_id should still exist (not removed).
    assert (
        entity_registry.async_get_entity_id(
            "switch", DOMAIN, f"{system.serial}_old_removed"
        )
        is not None
    )
