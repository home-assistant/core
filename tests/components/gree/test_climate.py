"""Tests for gree component."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from greeclimate.device import (
    TEMP_MAX,
    TEMP_MAX_F,
    TEMP_MIN,
    TEMP_MIN_F,
    HorizontalSwing,
    VerticalSwing,
)
from greeclimate.exceptions import DeviceNotBoundError, DeviceTimeoutError
from greeclimate.network import Response
import pytest
from pytest_homeassistant.common import async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_HORIZONTAL_MODE,
    ATTR_SWING_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    PRESET_SLEEP,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_HORIZONTAL_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.gree.climate import (
    FAN_MODES_INVERSE,
    HORIZONTAL_SWING_MODES_INVERSE,
    HVAC_MODES,
    HVAC_MODES_INVERSE,
    VERTICAL_SWING_MODES_INVERSE,
    GreeClimateEntity,
)
from homeassistant.components.gree.const import (
    FAN_MEDIUM_HIGH,
    FAN_MEDIUM_LOW,
    MAX_EXPECTED_RESPONSE_TIME_INTERVAL,
    UPDATE_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from .common import async_setup_gree, build_device_mock

ENTITY_ID = f"{CLIMATE_DOMAIN}.fake_device_1"


async def test_setup(hass: HomeAssistant) -> None:
    """Test a saved device creates its climate entity."""
    await async_setup_gree(hass)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.name == "fake-device-1"
    assert state.state == HVACMode.OFF


async def test_setup_connection_error(hass: HomeAssistant, device: MagicMock) -> None:
    """Test an unreachable saved device stays retryable without fresh entities."""
    device().bind.side_effect = DeviceNotBoundError

    entry = await async_setup_gree(hass)

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.states.get(ENTITY_ID) is None


async def test_setup_two_devices(
    hass: HomeAssistant, device: MagicMock, discovery: MagicMock
) -> None:
    """Test climate entities belong to separately enrolled devices."""
    first = device()
    second = build_device_mock(
        name="fake-device-2", ipAddress="2.2.2.2", identifier="bbccdd223344"
    )
    discovery.mock_devices = [first, second]
    device.side_effect = [first, second]

    first_entry = await async_setup_gree(hass, first)
    second_entry = await async_setup_gree(hass, second)

    assert len(hass.states.async_all(CLIMATE_DOMAIN)) == 2
    assert first_entry.unique_id == "aabbcc112233"
    assert second_entry.unique_id == "bbccdd223344"

    await hass.config_entries.async_unload(first_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get("climate.fake_device_2").state == HVACMode.OFF
    assert not second.closed


async def test_update_connection_failure(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, device: MagicMock
) -> None:
    """Test one timeout retains state and a second makes the device unavailable."""
    await async_setup_gree(hass)
    device().update_state.side_effect = DeviceTimeoutError

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == HVACMode.OFF
    assert device().update_state.await_count == 2

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_update_connection_send_failure_recovery(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, device: MagicMock
) -> None:
    """Test a successful poll after a failed send keeps the climate available."""
    await async_setup_gree(hass)
    device().update_state.side_effect = DeviceTimeoutError

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == HVACMode.OFF
    assert device().update_state.await_count == 2

    device().update_state.side_effect = None
    device().power = True
    device().mode = HVAC_MODES_INVERSE[HVACMode.COOL]
    freezer.tick(timedelta(seconds=UPDATE_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == HVACMode.COOL


async def test_update_unhandled_exception(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, device: MagicMock
) -> None:
    """Test an unexpected status error makes the climate unavailable."""
    await async_setup_gree(hass)
    device().update_state.side_effect = Exception

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_update_not_bound(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, device: MagicMock
) -> None:
    """Test an unbound device becomes unavailable on the first failed poll."""
    await async_setup_gree(hass)
    device().update_state.side_effect = DeviceNotBoundError

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_send_command_device_timeout(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, device: MagicMock
) -> None:
    """Test for sending power on command to the device with a device timeout."""
    await async_setup_gree(hass)

    freezer.tick(timedelta(seconds=UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.name == "fake-device-1"
    assert state.state != STATE_UNAVAILABLE

    device().push_state_update.side_effect = DeviceTimeoutError

    # Send failure should not raise exceptions or change device state
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_unresponsive_device(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, device: MagicMock
) -> None:
    """Test long response gaps and a RESULT restoring availability."""
    await async_setup_gree(hass)

    async def run_update() -> None:
        freezer.tick(timedelta(seconds=MAX_EXPECTED_RESPONSE_TIME_INTERVAL))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    await run_update()
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE

    await run_update()
    await run_update()
    await run_update()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    device().emit_response(Response.RESULT)
    await run_update()
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE


async def test_send_power_on(hass: HomeAssistant) -> None:
    """Test for sending power on command to the device."""
    await async_setup_gree(hass)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF


async def test_send_power_off_device_timeout(
    hass: HomeAssistant, device: MagicMock
) -> None:
    """Test for sending power off command to the device with a device timeout."""
    device().push_state_update.side_effect = DeviceTimeoutError

    await async_setup_gree(hass)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF


@pytest.mark.parametrize(
    ("units", "temperature"),
    [(METRIC_SYSTEM, 26), (US_CUSTOMARY_SYSTEM, 73)],
)
async def test_send_target_temperature(
    hass: HomeAssistant, device: MagicMock, units: UnitSystem, temperature: int
) -> None:
    """Test for sending target temperature command to the device."""
    hass.config.units = units

    device().power = True
    device().mode = HVAC_MODES_INVERSE.get(HVACMode.AUTO)

    fake_device = device()
    if units.temperature_unit == UnitOfTemperature.FAHRENHEIT:
        fake_device.temperature_units = 1

    await async_setup_gree(hass)

    # Make sure we're trying to test something that isn't the default
    assert fake_device.current_temperature != temperature

    hass.states.async_set(
        ENTITY_ID,
        "off",
        {
            ATTR_UNIT_OF_MEASUREMENT: units.temperature_unit,
        },
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: temperature},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_TEMPERATURE) == temperature
    assert state.state == HVAC_MODES.get(fake_device.mode)


@pytest.mark.parametrize(
    ("temperature", "hvac_mode"),
    [
        (26, HVACMode.OFF),
        (26, HVACMode.HEAT),
        (26, HVACMode.COOL),
        (26, HVACMode.AUTO),
        (26, HVACMode.DRY),
        (26, HVACMode.FAN_ONLY),
    ],
)
async def test_send_target_temperature_with_hvac_mode(
    hass: HomeAssistant, temperature: int, hvac_mode: HVACMode
) -> None:
    """Test for sending target temperature command to the device alongside hvac mode."""
    await async_setup_gree(hass)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TEMPERATURE: temperature,
            ATTR_HVAC_MODE: hvac_mode,
        },
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_TEMPERATURE) == temperature
    assert state.state == hvac_mode


@pytest.mark.parametrize(
    ("units", "temperature"),
    [
        (METRIC_SYSTEM, 25),
        (US_CUSTOMARY_SYSTEM, 73),
        (US_CUSTOMARY_SYSTEM, 74),
    ],
)
async def test_send_target_temperature_device_timeout(
    hass: HomeAssistant, device: MagicMock, units: UnitSystem, temperature: int
) -> None:
    """Test sending target temperature command with device timeout."""
    hass.config.units = units
    if units.temperature_unit == UnitOfTemperature.FAHRENHEIT:
        device().temperature_units = 1
    device().push_state_update.side_effect = DeviceTimeoutError

    await async_setup_gree(hass)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: temperature},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_TEMPERATURE) == temperature


@pytest.mark.parametrize(
    ("units", "temperature"),
    [
        (METRIC_SYSTEM, 25),
        (US_CUSTOMARY_SYSTEM, 73),
        (US_CUSTOMARY_SYSTEM, 74),
    ],
)
async def test_update_target_temperature(
    hass: HomeAssistant, device: MagicMock, units: UnitSystem, temperature: int
) -> None:
    """Test for updating target temperature from the device."""
    hass.config.units = units
    if units.temperature_unit == UnitOfTemperature.FAHRENHEIT:
        device().temperature_units = 1
    device().target_temperature = temperature

    await async_setup_gree(hass)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: temperature},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_TEMPERATURE) == temperature


@pytest.mark.parametrize(
    "preset", [PRESET_AWAY, PRESET_ECO, PRESET_SLEEP, PRESET_BOOST, PRESET_NONE]
)
async def test_send_preset_mode(hass: HomeAssistant, preset: str) -> None:
    """Test for sending preset mode command to the device."""
    await async_setup_gree(hass)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: preset},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_PRESET_MODE) == preset


async def test_send_invalid_preset_mode(hass: HomeAssistant) -> None:
    """Test for sending preset mode command to the device."""
    await async_setup_gree(hass)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: "invalid"},
            blocking=True,
        )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_PRESET_MODE) != "invalid"


@pytest.mark.parametrize(
    "preset", [PRESET_AWAY, PRESET_ECO, PRESET_SLEEP, PRESET_BOOST, PRESET_NONE]
)
async def test_send_preset_mode_device_timeout(
    hass: HomeAssistant, device: MagicMock, preset: str
) -> None:
    """Test for sending preset mode command to the device with a device timeout."""
    device().push_state_update.side_effect = DeviceTimeoutError

    await async_setup_gree(hass)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: preset},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_PRESET_MODE) == preset


@pytest.mark.parametrize(
    "preset", [PRESET_AWAY, PRESET_ECO, PRESET_SLEEP, PRESET_BOOST, PRESET_NONE]
)
async def test_update_preset_mode(
    hass: HomeAssistant, device: MagicMock, preset: str
) -> None:
    """Test for updating preset mode from the device."""
    device().steady_heat = preset == PRESET_AWAY
    device().power_save = preset == PRESET_ECO
    device().sleep = preset == PRESET_SLEEP
    device().turbo = preset == PRESET_BOOST

    await async_setup_gree(hass)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_PRESET_MODE) == preset


@pytest.mark.parametrize(
    "hvac_mode",
    [
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
        HVACMode.HEAT,
    ],
)
async def test_send_hvac_mode(hass: HomeAssistant, hvac_mode: HVACMode) -> None:
    """Test for sending hvac mode command to the device."""
    await async_setup_gree(hass)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == hvac_mode


@pytest.mark.parametrize(
    "hvac_mode",
    [HVACMode.AUTO, HVACMode.COOL, HVACMode.DRY, HVACMode.FAN_ONLY, HVACMode.HEAT],
)
async def test_send_hvac_mode_device_timeout(
    hass: HomeAssistant, device: MagicMock, hvac_mode: HVACMode
) -> None:
    """Test for sending hvac mode command to the device with a device timeout."""
    device().push_state_update.side_effect = DeviceTimeoutError

    await async_setup_gree(hass)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == hvac_mode


@pytest.mark.parametrize(
    "hvac_mode",
    [
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
        HVACMode.HEAT,
    ],
)
async def test_update_hvac_mode(
    hass: HomeAssistant, device: MagicMock, hvac_mode: HVACMode
) -> None:
    """Test for updating hvac mode from the device."""
    device().power = hvac_mode != HVACMode.OFF
    device().mode = HVAC_MODES_INVERSE.get(hvac_mode)

    await async_setup_gree(hass)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == hvac_mode


@pytest.mark.parametrize(
    "fan_mode",
    [FAN_AUTO, FAN_LOW, FAN_MEDIUM_LOW, FAN_MEDIUM, FAN_MEDIUM_HIGH, FAN_HIGH],
)
async def test_send_fan_mode(hass: HomeAssistant, fan_mode: str) -> None:
    """Test for sending fan mode command to the device."""
    await async_setup_gree(hass)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: fan_mode},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_FAN_MODE) == fan_mode


async def test_send_invalid_fan_mode(hass: HomeAssistant) -> None:
    """Test for sending fan mode command to the device."""
    await async_setup_gree(hass)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: "invalid"},
            blocking=True,
        )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_FAN_MODE) != "invalid"


@pytest.mark.parametrize(
    "fan_mode",
    [FAN_AUTO, FAN_LOW, FAN_MEDIUM_LOW, FAN_MEDIUM, FAN_MEDIUM_HIGH, FAN_HIGH],
)
async def test_send_fan_mode_device_timeout(
    hass: HomeAssistant, device: MagicMock, fan_mode: str
) -> None:
    """Test for sending fan mode command to the device with a device timeout."""
    device().push_state_update.side_effect = DeviceTimeoutError

    await async_setup_gree(hass)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: fan_mode},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_FAN_MODE) == fan_mode


@pytest.mark.parametrize(
    "fan_mode",
    [FAN_AUTO, FAN_LOW, FAN_MEDIUM_LOW, FAN_MEDIUM, FAN_MEDIUM_HIGH, FAN_HIGH],
)
async def test_update_fan_mode(
    hass: HomeAssistant, device: MagicMock, fan_mode: str
) -> None:
    """Test for updating fan mode from the device."""
    device().fan_speed = FAN_MODES_INVERSE.get(fan_mode)

    await async_setup_gree(hass)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_FAN_MODE) == fan_mode


@pytest.mark.parametrize(
    "swing_mode",
    ["default", "full_swing", "fixed_upper", "fixed_lower"],
)
async def test_send_swing_mode(hass: HomeAssistant, swing_mode: str) -> None:
    """Test for sending swing mode command to the device."""
    await async_setup_gree(hass)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SWING_MODE: swing_mode},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_SWING_MODE) == swing_mode


async def test_send_invalid_swing_mode(hass: HomeAssistant) -> None:
    """Test for sending swing mode command to the device."""
    await async_setup_gree(hass)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_SWING_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SWING_MODE: "invalid"},
            blocking=True,
        )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_SWING_MODE) != "invalid"


@pytest.mark.parametrize(
    "swing_mode",
    ["default", "full_swing", "fixed_upper", "fixed_lower"],
)
async def test_send_swing_mode_device_timeout(
    hass: HomeAssistant, device: MagicMock, swing_mode: str
) -> None:
    """Test for sending swing mode command to the device with a device timeout."""
    device().push_state_update.side_effect = DeviceTimeoutError

    await async_setup_gree(hass)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SWING_MODE: swing_mode},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_SWING_MODE) == swing_mode


@pytest.mark.parametrize(
    "vertical_swing",
    [VerticalSwing.Default, VerticalSwing.FullSwing, VerticalSwing.FixedUpper],
)
async def test_update_swing_mode(
    hass: HomeAssistant, device: MagicMock, vertical_swing: VerticalSwing
) -> None:
    """Test for updating swing mode from the device."""
    device().vertical_swing = vertical_swing

    await async_setup_gree(hass)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert (
        state.attributes.get(ATTR_SWING_MODE)
        == VERTICAL_SWING_MODES_INVERSE[vertical_swing]
    )


@pytest.mark.parametrize(
    "swing_horizontal_mode",
    ["default", "full_swing", "left", "right"],
)
async def test_send_swing_horizontal_mode(
    hass: HomeAssistant, swing_horizontal_mode: str
) -> None:
    """Test for sending horizontal swing mode command to the device."""
    await async_setup_gree(hass)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_HORIZONTAL_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SWING_HORIZONTAL_MODE: swing_horizontal_mode},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_SWING_HORIZONTAL_MODE) == swing_horizontal_mode


async def test_send_invalid_swing_horizontal_mode(hass: HomeAssistant) -> None:
    """Test for sending an invalid horizontal swing mode command to the device."""
    await async_setup_gree(hass)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_SWING_HORIZONTAL_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SWING_HORIZONTAL_MODE: "invalid"},
            blocking=True,
        )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_SWING_HORIZONTAL_MODE) != "invalid"


@pytest.mark.parametrize(
    "swing_horizontal_mode",
    ["default", "full_swing", "left", "right"],
)
async def test_send_swing_horizontal_mode_device_timeout(
    hass: HomeAssistant, device: MagicMock, swing_horizontal_mode: str
) -> None:
    """Test for sending horizontal swing mode command to the device with a device timeout."""
    device().push_state_update.side_effect = DeviceTimeoutError

    await async_setup_gree(hass)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_HORIZONTAL_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SWING_HORIZONTAL_MODE: swing_horizontal_mode},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_SWING_HORIZONTAL_MODE) == swing_horizontal_mode


@pytest.mark.parametrize(
    "horizontal_swing",
    [HorizontalSwing.Default, HorizontalSwing.FullSwing, HorizontalSwing.Left],
)
async def test_update_swing_horizontal_mode(
    hass: HomeAssistant, device: MagicMock, horizontal_swing: HorizontalSwing
) -> None:
    """Test for updating horizontal swing mode from the device."""
    device().horizontal_swing = horizontal_swing

    await async_setup_gree(hass)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert (
        state.attributes.get(ATTR_SWING_HORIZONTAL_MODE)
        == HORIZONTAL_SWING_MODES_INVERSE[horizontal_swing]
    )


async def test_swing_mode_unknown_device_value(
    hass: HomeAssistant, device: MagicMock
) -> None:
    """Test that an out-of-range vertical swing value from the device returns None."""
    device().vertical_swing = 99

    await async_setup_gree(hass)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_SWING_MODE) is None


async def test_swing_horizontal_mode_unknown_device_value(
    hass: HomeAssistant, device: MagicMock
) -> None:
    """Test that an out-of-range horizontal swing value from the device returns None."""
    device().horizontal_swing = 99

    await async_setup_gree(hass)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_SWING_HORIZONTAL_MODE) is None


@pytest.mark.parametrize(
    ("temperature_units", "expected_unit", "min_temp", "max_temp"),
    [
        (1, UnitOfTemperature.FAHRENHEIT, TEMP_MIN_F, TEMP_MAX_F),
        (0, UnitOfTemperature.CELSIUS, TEMP_MIN, TEMP_MAX),
    ],
)
async def test_coordinator_update_handler(
    hass: HomeAssistant,
    device: MagicMock,
    temperature_units: int,
    expected_unit: UnitOfTemperature,
    min_temp: int,
    max_temp: int,
) -> None:
    """A command response updates the entity's temperature unit and limits."""
    device().temperature_units = 1 - temperature_units
    await async_setup_gree(hass)
    entity: GreeClimateEntity = hass.data[CLIMATE_DOMAIN].get_entity(ENTITY_ID)

    device().temperature_units = temperature_units
    device().emit_response(Response.RESULT)
    await hass.async_block_till_done()

    assert entity.native_temperature_unit == expected_unit
    assert entity.min_temp == min_temp
    assert entity.max_temp == max_temp


@patch("homeassistant.components.gree.PLATFORMS", [CLIMATE_DOMAIN])
async def test_registry_settings(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Test for entity registry settings (unique_id)."""
    entry = await async_setup_gree(hass)

    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert entries == snapshot


@patch("homeassistant.components.gree.PLATFORMS", [CLIMATE_DOMAIN])
async def test_entity_states(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test for entity registry settings (unique_id)."""
    await async_setup_gree(hass)
    states = hass.states.async_all()
    assert states == snapshot
