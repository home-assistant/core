"""Tests for the xiaomi_miio services."""

from collections.abc import Generator
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, Mock, patch

from miio.powerstrip import PowerMode
import pytest

from homeassistant.components.xiaomi_miio.const import (
    CONF_FLOW_TYPE,
    DOMAIN,
    SERVICE_EYECARE_MODE_OFF,
    SERVICE_EYECARE_MODE_ON,
    SERVICE_NIGHT_LIGHT_MODE_OFF,
    SERVICE_NIGHT_LIGHT_MODE_ON,
    SERVICE_REMINDER_OFF,
    SERVICE_REMINDER_ON,
    SERVICE_RESET_FILTER,
    SERVICE_SET_DELAYED_TURN_OFF,
    SERVICE_SET_EXTRA_FEATURES,
    SERVICE_SET_POWER_MODE,
    SERVICE_SET_POWER_PRICE,
    SERVICE_SET_SCENE,
    SERVICE_SET_WIFI_LED_OFF,
    SERVICE_SET_WIFI_LED_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_MODE,
    CONF_DEVICE,
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_TOKEN,
    ENTITY_MATCH_ALL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import TEST_MAC

from tests.common import MockConfigEntry, async_fire_time_changed

EYECARE_MODEL = "philips.light.sread1"
POWER_STRIP_MODEL = "qmi.powerstrip.v1"
AIR_PURIFIER_MODEL = "zhimi.airpurifier.m1"
EYECARE_ENTITY_ID = "light.test_device"
AMBIENT_ENTITY_ID = "light.test_device_ambient_light"
POWER_STRIP_ENTITY_ID = "switch.test_device"
AIR_PURIFIER_ENTITY_ID = "fan.test_device"


async def setup_device(
    hass: HomeAssistant, model: str, platform: Platform
) -> MockConfigEntry:
    """Set up a xiaomi_miio device."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="123456",
        title="Test Device",
        data={
            CONF_FLOW_TYPE: CONF_DEVICE,
            CONF_HOST: "192.168.1.100",
            CONF_TOKEN: "12345678901234567890123456789012",
            CONF_MODEL: model,
            CONF_MAC: TEST_MAC,
        },
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.xiaomi_miio.get_platforms", return_value=[platform]
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # The entity starts out unavailable, and the entity service helper does not
    # select unavailable entities, so let it poll the device once
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=60))
    await hass.async_block_till_done()
    return config_entry


@pytest.fixture(name="mock_light")
def mock_light_fixture() -> Generator[MagicMock]:
    """Mock an eyecare lamp, which implements every light service."""
    mock_light = MagicMock()
    mock_light.status = Mock(
        return_value=Mock(
            is_on=True,
            brightness=50,
            color_temperature=50,
            scene=1,
            delay_off_countdown=0,
            smart_night_light=False,
            eyecare=False,
            reminder=False,
            ambient=False,
            ambient_brightness=0,
        )
    )
    with patch(
        "homeassistant.components.xiaomi_miio.light.PhilipsEyecare",
        return_value=mock_light,
    ):
        yield mock_light


@pytest.fixture(name="mock_switch")
def mock_switch_fixture() -> Generator[MagicMock]:
    """Mock a power strip, which implements every switch service."""
    mock_switch = MagicMock()
    mock_switch.status = Mock(
        return_value=Mock(
            is_on=True,
            temperature=30,
            load_power=10,
            mode=None,
            wifi_led=None,
            power_price=None,
        )
    )
    with patch(
        "homeassistant.components.xiaomi_miio.switch.PowerStrip",
        return_value=mock_switch,
    ):
        yield mock_switch


@pytest.fixture(name="mock_fan")
def mock_fan_fixture() -> Generator[MagicMock]:
    """Mock an air purifier, which implements every fan service."""
    mock_fan = MagicMock()
    mock_fan.status = Mock(return_value=Mock(is_on=True))
    with patch(
        "homeassistant.components.xiaomi_miio.AirPurifier", return_value=mock_fan
    ):
        yield mock_fan


@pytest.mark.parametrize(
    ("service", "service_data", "device_method", "device_args"),
    [
        pytest.param(
            SERVICE_SET_SCENE, {"scene": 2}, "set_scene", (2,), id="set_scene"
        ),
        pytest.param(
            SERVICE_SET_DELAYED_TURN_OFF,
            {"time_period": 300},
            "delay_off",
            (5,),
            id="set_delayed_turn_off",
        ),
        pytest.param(SERVICE_REMINDER_ON, {}, "reminder_on", (), id="reminder_on"),
        pytest.param(SERVICE_REMINDER_OFF, {}, "reminder_off", (), id="reminder_off"),
        pytest.param(
            SERVICE_NIGHT_LIGHT_MODE_ON,
            {},
            "smart_night_light_on",
            (),
            id="night_light_mode_on",
        ),
        pytest.param(
            SERVICE_NIGHT_LIGHT_MODE_OFF,
            {},
            "smart_night_light_off",
            (),
            id="night_light_mode_off",
        ),
        pytest.param(SERVICE_EYECARE_MODE_ON, {}, "eyecare_on", (), id="eyecare_on"),
        pytest.param(SERVICE_EYECARE_MODE_OFF, {}, "eyecare_off", (), id="eyecare_off"),
    ],
)
@pytest.mark.usefixtures("mock_light")
async def test_light_services(
    hass: HomeAssistant,
    mock_light: MagicMock,
    service: str,
    service_data: dict[str, Any],
    device_method: str,
    device_args: tuple[Any, ...],
) -> None:
    """Test the light services reach the device."""
    await setup_device(hass, EYECARE_MODEL, Platform.LIGHT)

    await hass.services.async_call(
        DOMAIN,
        service,
        {ATTR_ENTITY_ID: EYECARE_ENTITY_ID} | service_data,
        blocking=True,
    )

    getattr(mock_light, device_method).assert_called_once_with(*device_args)


@pytest.mark.parametrize(
    ("service", "service_data", "device_method", "device_args"),
    [
        pytest.param(
            SERVICE_SET_WIFI_LED_ON, {}, "set_wifi_led", (True,), id="set_wifi_led_on"
        ),
        pytest.param(
            SERVICE_SET_WIFI_LED_OFF,
            {},
            "set_wifi_led",
            (False,),
            id="set_wifi_led_off",
        ),
        pytest.param(
            SERVICE_SET_POWER_MODE,
            {ATTR_MODE: "green"},
            "set_power_mode",
            (PowerMode.Eco,),
            id="set_power_mode",
        ),
        pytest.param(
            SERVICE_SET_POWER_PRICE,
            {"price": 3},
            "set_power_price",
            (3.0,),
            id="set_power_price",
        ),
    ],
)
@pytest.mark.usefixtures("mock_switch")
async def test_switch_services(
    hass: HomeAssistant,
    mock_switch: MagicMock,
    service: str,
    service_data: dict[str, Any],
    device_method: str,
    device_args: tuple[Any, ...],
) -> None:
    """Test the switch services reach the device."""
    await setup_device(hass, POWER_STRIP_MODEL, Platform.SWITCH)

    await hass.services.async_call(
        DOMAIN,
        service,
        {ATTR_ENTITY_ID: POWER_STRIP_ENTITY_ID} | service_data,
        blocking=True,
    )

    getattr(mock_switch, device_method).assert_called_once_with(*device_args)


@pytest.mark.usefixtures("mock_light")
async def test_service_skips_entities_without_the_method(
    hass: HomeAssistant, mock_light: MagicMock
) -> None:
    """Test entities not implementing the method are skipped, not an error."""
    await setup_device(hass, EYECARE_MODEL, Platform.LIGHT)

    # The ambient light is on the same platform but has no async_set_scene
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_SCENE,
        {ATTR_ENTITY_ID: AMBIENT_ENTITY_ID, "scene": 2},
        blocking=True,
    )
    mock_light.set_scene.assert_not_called()

    # Targeting every entity reaches the eyecare lamp and skips the rest
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_SCENE,
        {ATTR_ENTITY_ID: ENTITY_MATCH_ALL, "scene": 2},
        blocking=True,
    )
    mock_light.set_scene.assert_called_once_with(2)


@pytest.mark.parametrize(
    ("service", "service_data", "device_method", "device_args"),
    [
        pytest.param(SERVICE_RESET_FILTER, {}, "reset_filter", (), id="reset_filter"),
        pytest.param(
            SERVICE_SET_EXTRA_FEATURES,
            {"features": 1},
            "set_extra_features",
            (1,),
            id="set_extra_features",
        ),
    ],
)
@pytest.mark.usefixtures("mock_fan")
async def test_fan_services(
    hass: HomeAssistant,
    mock_fan: MagicMock,
    service: str,
    service_data: dict[str, Any],
    device_method: str,
    device_args: tuple[Any, ...],
) -> None:
    """Test the fan services reach the device."""
    await setup_device(hass, AIR_PURIFIER_MODEL, Platform.FAN)

    await hass.services.async_call(
        DOMAIN,
        service,
        {ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID} | service_data,
        blocking=True,
    )

    getattr(mock_fan, device_method).assert_called_once_with(*device_args)
