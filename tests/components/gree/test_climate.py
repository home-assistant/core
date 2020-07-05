"""Tests for gree component."""
from datetime import timedelta

from greeclimate.exceptions import DeviceTimeoutError
import pytest

from homeassistant.components.climate.const import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    DOMAIN,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    PRESET_SLEEP,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
)
from homeassistant.components.gree.climate import SUPPORTED_FEATURES
from homeassistant.components.gree.const import (
    DOMAIN as GREE_DOMAIN,
    FAN_MEDIUMHIGH,
    FAN_MEDIUMLOW,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
)
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.async_mock import DEFAULT as DEFAULT_MOCK, AsyncMock, Mock, patch
from tests.common import async_fire_time_changed

ENTITY_ID = f"{DOMAIN}.fake"

MOCK_CONFIG = {GREE_DOMAIN: {}}


def _build_device_info_mock():
    mock = Mock(ip="1.1.1.1", port=7000, mac="aabbcc112233")
    mock.name = "fake"
    return mock


def _build_device_mock():
    mock = Mock(
        device_info=_build_device_info_mock(),
        name="fake-device-1",
        bind=AsyncMock(),
        update_state=AsyncMock(),
        push_state_update=AsyncMock(),
        temperature_units=0,
        mode=0,
        fan_speed=0,
        horizontal_swing=0,
        vertical_swing=0,
        target_temperature=25,
        power=False,
        sleep=False,
        quiet=False,
        turbo=False,
        power_save=False,
        steady_heat=False,
    )
    return mock


@pytest.fixture(name="discovery")
def discovery_fixture():
    """Patch the discovery service."""
    with patch(
        "homeassistant.components.gree.bridge.GreeClimate.search_devices",
        new_callable=AsyncMock,
        return_value=[_build_device_info_mock],
    ) as mock:
        yield mock


@pytest.fixture(name="device")
def device_fixture():
    """Path the device search and bind."""
    with patch(
        "homeassistant.components.gree.bridge.Device",
        return_value=_build_device_mock(),
    ) as mock:
        yield mock


@pytest.fixture(name="gethostname")
def hostname_fixture():
    """Patch the hostname lookup service."""
    with patch("homeassistant.components.gree.bridge.socket") as mock:
        mock.gethostbyname.return_value = "1.1.1.1"
        yield mock


@pytest.fixture
def mock_now():
    """Fixture for dtutil.now."""
    return dt_util.utcnow()


async def setup_gree(hass, config):
    """Set up mock Gree."""
    await async_setup_component(hass, GREE_DOMAIN, config)
    await hass.async_block_till_done()


async def test_setup(hass, discovery, device, gethostname):
    """Test setup of platform."""
    await setup_gree(hass, MOCK_CONFIG)
    assert hass.states.get(ENTITY_ID)


async def test_update_connection_failure(
    hass, discovery, device, gethostname, mock_now
):
    """Testing update hvac connection failure exception."""
    device().update_state.side_effect = [
        DEFAULT_MOCK,
        DeviceTimeoutError,
        DeviceTimeoutError,
    ]

    await setup_gree(hass, MOCK_CONFIG)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    # First update to make the device available
    state = hass.states.get(ENTITY_ID)
    assert state.name == "fake"
    assert state.state != STATE_UNAVAILABLE

    next_update = mock_now + timedelta(minutes=10)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    next_update = mock_now + timedelta(minutes=15)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    # Then two more update failures to make the device unavailable
    state = hass.states.get(ENTITY_ID)
    assert state.name == "fake"
    assert state.state == STATE_UNAVAILABLE


async def test_update_connection_failure_recovery(
    hass, discovery, device, gethostname, mock_now
):
    """Testing update hvac connection failure recovery."""
    device().update_state.side_effect = [DeviceTimeoutError, DEFAULT_MOCK]

    await setup_gree(hass, MOCK_CONFIG)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.name == "fake"
    assert state.state == STATE_UNAVAILABLE

    next_update = mock_now + timedelta(minutes=10)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.name == "fake"
    assert state.state != STATE_UNAVAILABLE


async def test_update_unhandled_exception(
    hass, discovery, device, gethostname, mock_now
):
    """Testing update hvac connection unhandled response exception."""
    device().update_state.side_effect = [DEFAULT_MOCK, Exception]

    await setup_gree(hass, MOCK_CONFIG)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.name == "fake"
    assert state.state != STATE_UNAVAILABLE

    next_update = mock_now + timedelta(minutes=10)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.name == "fake"
    assert state.state == STATE_UNAVAILABLE


async def test_send_command_device_timeout(
    hass, discovery, device, gethostname, mock_now
):
    """Test for sending power on command to the device with a device timeout."""
    device().update_state.side_effect = [DEFAULT_MOCK, DeviceTimeoutError]
    device().push_state_update.side_effect = DeviceTimeoutError

    await setup_gree(hass, MOCK_CONFIG)

    # First update to make the device available
    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.name == "fake"
    assert state.state != STATE_UNAVAILABLE

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVAC_MODE_AUTO},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_send_command_device_unknown_error(
    hass, discovery, device, gethostname, mock_now
):
    """Test for sending power on command to the device with a device timeout."""
    device().update_state.side_effect = [DEFAULT_MOCK, Exception]
    device().push_state_update.side_effect = Exception

    await setup_gree(hass, MOCK_CONFIG)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    # First update to make the device available
    state = hass.states.get(ENTITY_ID)
    assert state.name == "fake"
    assert state.state != STATE_UNAVAILABLE

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVAC_MODE_AUTO},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_send_power_on(hass, discovery, device, gethostname, mock_now):
    """Test for sending power on command to the device."""
    await setup_gree(hass, MOCK_CONFIG)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVAC_MODE_AUTO},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVAC_MODE_AUTO


async def test_send_power_on_device_timeout(
    hass, discovery, device, gethostname, mock_now
):
    """Test for sending power on command to the device with a device timeout."""
    device().push_state_update.side_effect = DeviceTimeoutError

    await setup_gree(hass, MOCK_CONFIG)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVAC_MODE_AUTO},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == HVAC_MODE_AUTO


async def test_send_target_temperature(hass, discovery, device, gethostname, mock_now):
    """Test for sending target temperature command to the device."""
    await setup_gree(hass, MOCK_CONFIG)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 25.1},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_TEMPERATURE) == 25


async def test_send_target_temperature_device_timeout(
    hass, discovery, device, gethostname, mock_now
):
    """Test for sending target temperature command to the device with a device timeout."""
    device().push_state_update.side_effect = DeviceTimeoutError

    await setup_gree(hass, MOCK_CONFIG)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 25.1},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_TEMPERATURE) == 25


@pytest.mark.parametrize(
    "preset", (PRESET_AWAY, PRESET_ECO, PRESET_SLEEP, PRESET_BOOST, PRESET_NONE)
)
async def test_send_preset_mode(hass, discovery, device, gethostname, mock_now, preset):
    """Test for sending preset mode command to the device."""
    await setup_gree(hass, MOCK_CONFIG)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: preset},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_PRESET_MODE) == preset


async def test_send_invalid_preset_mode(hass, discovery, device, gethostname, mock_now):
    """Test for sending preset mode command to the device."""
    await setup_gree(hass, MOCK_CONFIG)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: "invalid"},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_PRESET_MODE) != "invalid"


@pytest.mark.parametrize(
    "preset", (PRESET_AWAY, PRESET_ECO, PRESET_SLEEP, PRESET_BOOST, PRESET_NONE)
)
async def test_send_preset_mode_device_timeout(
    hass, discovery, device, gethostname, mock_now, preset
):
    """Test for sending preset mode command to the device with a device timeout."""
    device().push_state_update.side_effect = DeviceTimeoutError

    await setup_gree(hass, MOCK_CONFIG)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: preset},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_PRESET_MODE) == preset


@pytest.mark.parametrize(
    "hvac_mode",
    (HVAC_MODE_AUTO, HVAC_MODE_COOL, HVAC_MODE_DRY, HVAC_MODE_FAN_ONLY, HVAC_MODE_HEAT),
)
async def test_send_hvac_mode(
    hass, discovery, device, gethostname, mock_now, hvac_mode
):
    """Test for sending hvac mode command to the device."""
    await setup_gree(hass, MOCK_CONFIG)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == hvac_mode


@pytest.mark.parametrize(
    "hvac_mode",
    (HVAC_MODE_AUTO, HVAC_MODE_COOL, HVAC_MODE_DRY, HVAC_MODE_FAN_ONLY, HVAC_MODE_HEAT),
)
async def test_send_hvac_mode_device_timeout(
    hass, discovery, device, gethostname, mock_now, hvac_mode
):
    """Test for sending hvac mode command to the device with a device timeout."""
    device().push_state_update.side_effect = DeviceTimeoutError

    await setup_gree(hass, MOCK_CONFIG)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == hvac_mode


@pytest.mark.parametrize(
    "fan_mode", (FAN_AUTO, FAN_LOW, FAN_MEDIUMLOW, FAN_MEDIUM, FAN_MEDIUMHIGH, FAN_HIGH)
)
async def test_send_fan_mode(hass, discovery, device, gethostname, mock_now, fan_mode):
    """Test for sending fan mode command to the device."""
    await setup_gree(hass, MOCK_CONFIG)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: fan_mode},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_FAN_MODE) == fan_mode


async def test_send_invalid_fan_mode(hass, discovery, device, gethostname, mock_now):
    """Test for sending fan mode command to the device."""
    await setup_gree(hass, MOCK_CONFIG)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: "invalid"},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_FAN_MODE) != "invalid"


@pytest.mark.parametrize(
    "fan_mode", (FAN_AUTO, FAN_LOW, FAN_MEDIUMLOW, FAN_MEDIUM, FAN_MEDIUMHIGH, FAN_HIGH)
)
async def test_send_fan_mode_device_timeout(
    hass, discovery, device, gethostname, mock_now, fan_mode
):
    """Test for sending fan mode command to the device with a device timeout."""
    device().push_state_update.side_effect = DeviceTimeoutError

    await setup_gree(hass, MOCK_CONFIG)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: fan_mode},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_FAN_MODE) == fan_mode


@pytest.mark.parametrize(
    "swing_mode", (SWING_OFF, SWING_BOTH, SWING_VERTICAL, SWING_HORIZONTAL)
)
async def test_send_swing_mode(
    hass, discovery, device, gethostname, mock_now, swing_mode
):
    """Test for sending swing mode command to the device."""
    await setup_gree(hass, MOCK_CONFIG)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SWING_MODE: swing_mode},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_SWING_MODE) == swing_mode


async def test_send_invalid_swing_mode(hass, discovery, device, gethostname, mock_now):
    """Test for sending swing mode command to the device."""
    await setup_gree(hass, MOCK_CONFIG)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SWING_MODE: "invalid"},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_SWING_MODE) != "invalid"


@pytest.mark.parametrize(
    "swing_mode", (SWING_OFF, SWING_BOTH, SWING_VERTICAL, SWING_HORIZONTAL)
)
async def test_send_swing_mode_device_timeout(
    hass, discovery, device, gethostname, mock_now, swing_mode
):
    """Test for sending swing mode command to the device with a device timeout."""
    device().push_state_update.side_effect = DeviceTimeoutError

    await setup_gree(hass, MOCK_CONFIG)

    next_update = mock_now + timedelta(minutes=5)
    with patch("homeassistant.util.dt.utcnow", return_value=next_update):
        async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()

    assert await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SWING_MODE: swing_mode},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_SWING_MODE) == swing_mode


async def test_name(hass, discovery, device, gethostname):
    """Test for name property."""
    await setup_gree(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_FRIENDLY_NAME] == "fake"


async def test_supported_features_with_turnon(hass, discovery, device, gethostname):
    """Test for supported_features property."""
    await setup_gree(hass, MOCK_CONFIG)
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == SUPPORTED_FEATURES
