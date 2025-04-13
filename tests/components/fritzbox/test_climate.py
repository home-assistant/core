"""Tests for AVM Fritz!Box climate component."""

from datetime import timedelta
from unittest.mock import Mock, _Call, call, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from requests.exceptions import HTTPError
from syrupy import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.fritzbox.climate import (
    OFF_API_TEMPERATURE,
    ON_API_TEMPERATURE,
    PRESET_HOLIDAY,
    PRESET_SUMMER,
)
from homeassistant.components.fritzbox.const import (
    ATTR_STATE_HOLIDAY_MODE,
    ATTR_STATE_SUMMER_MODE,
    DOMAIN as FB_DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, CONF_DEVICES, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import (
    FritzDeviceClimateMock,
    FritzDeviceClimateWithoutTempSensorMock,
    set_devices,
    setup_config_entry,
)
from .const import CONF_FAKE_NAME, MOCK_CONFIG

from tests.common import async_fire_time_changed, snapshot_platform

ENTITY_ID = f"{CLIMATE_DOMAIN}.{CONF_FAKE_NAME}"


async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    fritz: Mock,
) -> None:
    """Test setup of platform."""
    device = FritzDeviceClimateMock()
    with patch("homeassistant.components.fritzbox.PLATFORMS", [Platform.CLIMATE]):
        entry = await setup_config_entry(
            hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
        )

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_hkr_wo_temperature_sensor(hass: HomeAssistant, fritz: Mock) -> None:
    """Test hkr without exposing dedicated temperature sensor data block."""
    device = FritzDeviceClimateWithoutTempSensorMock()
    await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 18.0


async def test_target_temperature_on(hass: HomeAssistant, fritz: Mock) -> None:
    """Test turn device on."""
    device = FritzDeviceClimateMock()
    device.target_temperature = 127.0
    await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_TEMPERATURE] is None


async def test_target_temperature_off(hass: HomeAssistant, fritz: Mock) -> None:
    """Test turn device on."""
    device = FritzDeviceClimateMock()
    device.target_temperature = 126.5
    await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_TEMPERATURE] is None


async def test_update(hass: HomeAssistant, fritz: Mock) -> None:
    """Test update without error."""
    device = FritzDeviceClimateMock()
    await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 18
    assert state.attributes[ATTR_MAX_TEMP] == 28
    assert state.attributes[ATTR_MIN_TEMP] == 8
    assert state.attributes[ATTR_TEMPERATURE] == 19.5

    device.temperature = 19
    device.target_temperature = 20

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get(ENTITY_ID)

    assert fritz().update_devices.call_count == 2
    assert state
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 19
    assert state.attributes[ATTR_TEMPERATURE] == 20


async def test_automatic_offset(hass: HomeAssistant, fritz: Mock) -> None:
    """Test when automatic offset is configured on fritz!box device."""
    device = FritzDeviceClimateMock()
    device.temperature = 18
    device.actual_temperature = 19
    device.target_temperature = 20
    await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 18
    assert state.attributes[ATTR_MAX_TEMP] == 28
    assert state.attributes[ATTR_MIN_TEMP] == 8
    assert state.attributes[ATTR_TEMPERATURE] == 20


async def test_update_error(hass: HomeAssistant, fritz: Mock) -> None:
    """Test update with error."""
    device = FritzDeviceClimateMock()
    fritz().update_devices.side_effect = HTTPError("Boom")
    entry = await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )
    assert entry.state is ConfigEntryState.SETUP_RETRY

    assert fritz().update_devices.call_count == 2
    assert fritz().login.call_count == 2

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert fritz().update_devices.call_count == 4
    assert fritz().login.call_count == 4


@pytest.mark.parametrize(
    (
        "service_data",
        "expected_set_target_temperature_call_args",
        "expected_set_hkr_state_call_args",
    ),
    [
        ({ATTR_TEMPERATURE: 23}, [call(23, True)], []),
        (
            {
                ATTR_HVAC_MODE: HVACMode.OFF,
                ATTR_TEMPERATURE: 23,
            },
            [],
            [call("off", True)],
        ),
        (
            {
                ATTR_HVAC_MODE: HVACMode.HEAT,
                ATTR_TEMPERATURE: 23,
            },
            [call(23, True)],
            [],
        ),
    ],
)
async def test_set_temperature(
    hass: HomeAssistant,
    fritz: Mock,
    service_data: dict,
    expected_set_target_temperature_call_args: list[_Call],
    expected_set_hkr_state_call_args: list[_Call],
) -> None:
    """Test setting temperature."""
    device = FritzDeviceClimateMock()
    await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        True,
    )
    assert device.set_target_temperature.call_count == len(
        expected_set_target_temperature_call_args
    )
    assert (
        device.set_target_temperature.call_args_list
        == expected_set_target_temperature_call_args
    )
    assert device.set_hkr_state.call_count == len(expected_set_hkr_state_call_args)
    assert device.set_hkr_state.call_args_list == expected_set_hkr_state_call_args


@pytest.mark.parametrize(
    (
        "service_data",
        "target_temperature",
        "current_preset",
        "expected_set_target_temperature_call_args",
        "expected_set_hkr_state_call_args",
    ),
    [
        # mode off always sets hkr state off
        ({ATTR_HVAC_MODE: HVACMode.OFF}, 22, PRESET_COMFORT, [], [call("off", True)]),
        ({ATTR_HVAC_MODE: HVACMode.OFF}, 16, PRESET_ECO, [], [call("off", True)]),
        ({ATTR_HVAC_MODE: HVACMode.OFF}, 16, None, [], [call("off", True)]),
        # mode heat sets target temperature based on current scheduled preset,
        # when not already in mode heat
        (
            {ATTR_HVAC_MODE: HVACMode.HEAT},
            OFF_API_TEMPERATURE,
            PRESET_COMFORT,
            [call(22, True)],
            [],
        ),
        (
            {ATTR_HVAC_MODE: HVACMode.HEAT},
            OFF_API_TEMPERATURE,
            PRESET_ECO,
            [call(16, True)],
            [],
        ),
        (
            {ATTR_HVAC_MODE: HVACMode.HEAT},
            OFF_API_TEMPERATURE,
            None,
            [call(22, True)],
            [],
        ),
        # mode heat does not set target temperature, when already in mode heat
        ({ATTR_HVAC_MODE: HVACMode.HEAT}, 16, PRESET_COMFORT, [], []),
        ({ATTR_HVAC_MODE: HVACMode.HEAT}, 16, PRESET_ECO, [], []),
        ({ATTR_HVAC_MODE: HVACMode.HEAT}, 16, None, [], []),
        ({ATTR_HVAC_MODE: HVACMode.HEAT}, 22, PRESET_COMFORT, [], []),
        ({ATTR_HVAC_MODE: HVACMode.HEAT}, 22, PRESET_ECO, [], []),
        ({ATTR_HVAC_MODE: HVACMode.HEAT}, 22, None, [], []),
    ],
)
async def test_set_hvac_mode(
    hass: HomeAssistant,
    fritz: Mock,
    service_data: dict,
    target_temperature: float,
    current_preset: str,
    expected_set_target_temperature_call_args: list[_Call],
    expected_set_hkr_state_call_args: list[_Call],
) -> None:
    """Test setting hvac mode."""
    device = FritzDeviceClimateMock()
    device.target_temperature = target_temperature

    if current_preset is PRESET_COMFORT:
        device.nextchange_temperature = device.eco_temperature
    elif current_preset is PRESET_ECO:
        device.nextchange_temperature = device.comfort_temperature
    else:
        device.nextchange_endperiod = 0

    await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        True,
    )

    assert device.set_target_temperature.call_count == len(
        expected_set_target_temperature_call_args
    )
    assert (
        device.set_target_temperature.call_args_list
        == expected_set_target_temperature_call_args
    )
    assert device.set_hkr_state.call_count == len(expected_set_hkr_state_call_args)
    assert device.set_hkr_state.call_args_list == expected_set_hkr_state_call_args


@pytest.mark.parametrize(
    ("comfort_temperature", "expected_call_args"),
    [
        (20, [call("comfort", True)]),
        (28, [call("comfort", True)]),
        (ON_API_TEMPERATURE, [call("comfort", True)]),
    ],
)
async def test_set_preset_mode_comfort(
    hass: HomeAssistant,
    fritz: Mock,
    comfort_temperature: int,
    expected_call_args: list[_Call],
) -> None:
    """Test setting preset mode."""
    device = FritzDeviceClimateMock()
    device.comfort_temperature = comfort_temperature
    await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_COMFORT},
        True,
    )
    assert device.set_hkr_state.call_count == len(expected_call_args)
    assert device.set_hkr_state.call_args_list == expected_call_args


@pytest.mark.parametrize(
    ("eco_temperature", "expected_call_args"),
    [
        (20, [call("eco", True)]),
        (16, [call("eco", True)]),
        (OFF_API_TEMPERATURE, [call("eco", True)]),
    ],
)
async def test_set_preset_mode_eco(
    hass: HomeAssistant,
    fritz: Mock,
    eco_temperature: int,
    expected_call_args: list[_Call],
) -> None:
    """Test setting preset mode."""
    device = FritzDeviceClimateMock()
    device.eco_temperature = eco_temperature
    await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_ECO},
        True,
    )
    assert device.set_hkr_state.call_count == len(expected_call_args)
    assert device.set_hkr_state.call_args_list == expected_call_args


async def test_set_preset_mode_boost(
    hass: HomeAssistant,
    fritz: Mock,
) -> None:
    """Test setting preset mode."""
    device = FritzDeviceClimateMock()
    await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_BOOST},
        True,
    )
    assert device.set_hkr_state.call_count == 1
    assert device.set_hkr_state.call_args_list == [call("on", True)]


async def test_preset_mode_update(hass: HomeAssistant, fritz: Mock) -> None:
    """Test preset mode."""
    device = FritzDeviceClimateMock()
    device.comfort_temperature = 23
    device.eco_temperature = 20
    await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_PRESET_MODE] is None

    # test comfort preset
    device.target_temperature = 23
    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get(ENTITY_ID)

    assert fritz().update_devices.call_count == 2
    assert state
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_COMFORT

    # test eco preset
    device.target_temperature = 20
    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get(ENTITY_ID)

    assert fritz().update_devices.call_count == 3
    assert state
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_ECO

    # test boost preset
    device.target_temperature = 127  # special temp from the api
    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get(ENTITY_ID)

    assert fritz().update_devices.call_count == 4
    assert state
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_BOOST


async def test_discover_new_device(hass: HomeAssistant, fritz: Mock) -> None:
    """Test adding new discovered devices during runtime."""
    device = FritzDeviceClimateMock()
    await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    state = hass.states.get(ENTITY_ID)
    assert state

    new_device = FritzDeviceClimateMock()
    new_device.ain = "7890 1234"
    new_device.name = "new_climate"
    set_devices(fritz, devices=[device, new_device])

    next_update = dt_util.utcnow() + timedelta(seconds=200)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(f"{CLIMATE_DOMAIN}.new_climate")
    assert state


async def test_holidy_summer_mode(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, fritz: Mock
) -> None:
    """Test holiday and summer mode."""
    device = FritzDeviceClimateMock()
    await setup_config_entry(
        hass, MOCK_CONFIG[FB_DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )

    # initial state
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_STATE_HOLIDAY_MODE] is False
    assert state.attributes[ATTR_STATE_SUMMER_MODE] is False
    assert state.attributes[ATTR_HVAC_MODES] == [HVACMode.HEAT, HVACMode.OFF]
    assert state.attributes[ATTR_PRESET_MODE] is None
    assert state.attributes[ATTR_PRESET_MODES] == [
        PRESET_ECO,
        PRESET_COMFORT,
        PRESET_BOOST,
    ]

    # test holiday mode
    device.holiday_active = True
    device.summer_active = False
    freezer.tick(timedelta(seconds=200))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_STATE_HOLIDAY_MODE]
    assert state.attributes[ATTR_STATE_SUMMER_MODE] is False
    assert state.attributes[ATTR_HVAC_MODES] == [HVACMode.HEAT]
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_HOLIDAY
    assert state.attributes[ATTR_PRESET_MODES] == [PRESET_HOLIDAY]

    with pytest.raises(
        HomeAssistantError,
        match="Can't change HVAC mode while holiday or summer mode is active on the device",
    ):
        await hass.services.async_call(
            "climate",
            SERVICE_SET_HVAC_MODE,
            {"entity_id": ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
            blocking=True,
        )
    with pytest.raises(
        HomeAssistantError,
        match="Can't change preset while holiday or summer mode is active on the device",
    ):
        await hass.services.async_call(
            "climate",
            SERVICE_SET_PRESET_MODE,
            {"entity_id": ENTITY_ID, ATTR_PRESET_MODE: PRESET_HOLIDAY},
            blocking=True,
        )

    # test summer mode
    device.holiday_active = False
    device.summer_active = True
    freezer.tick(timedelta(seconds=200))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_STATE_HOLIDAY_MODE] is False
    assert state.attributes[ATTR_STATE_SUMMER_MODE]
    assert state.attributes[ATTR_HVAC_MODES] == [HVACMode.OFF]
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_SUMMER
    assert state.attributes[ATTR_PRESET_MODES] == [PRESET_SUMMER]

    with pytest.raises(
        HomeAssistantError,
        match="Can't change HVAC mode while holiday or summer mode is active on the device",
    ):
        await hass.services.async_call(
            "climate",
            SERVICE_SET_HVAC_MODE,
            {"entity_id": ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
            blocking=True,
        )
    with pytest.raises(
        HomeAssistantError,
        match="Can't change preset while holiday or summer mode is active on the device",
    ):
        await hass.services.async_call(
            "climate",
            SERVICE_SET_PRESET_MODE,
            {"entity_id": ENTITY_ID, ATTR_PRESET_MODE: PRESET_SUMMER},
            blocking=True,
        )

    # back to normal state
    device.holiday_active = False
    device.summer_active = False
    freezer.tick(timedelta(seconds=200))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_STATE_HOLIDAY_MODE] is False
    assert state.attributes[ATTR_STATE_SUMMER_MODE] is False
    assert state.attributes[ATTR_HVAC_MODES] == [HVACMode.HEAT, HVACMode.OFF]
    assert state.attributes[ATTR_PRESET_MODE] is None
    assert state.attributes[ATTR_PRESET_MODES] == [
        PRESET_ECO,
        PRESET_COMFORT,
        PRESET_BOOST,
    ]
