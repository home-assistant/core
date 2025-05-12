"""Define fixtures available for all tests."""

from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from habluetooth import BluetoothServiceInfoBleak
import pytest
from switchbot import SwitchbotModel

from homeassistant.components.switchbot import ENCRYPTED_MODELS
from homeassistant.components.switchbot.const import (
    CONF_ENCRYPTION_KEY,
    CONF_KEY_ID,
    DOMAIN,
    SUPPORTED_MODEL_TYPES,
)
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_SENSOR_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import BLUETOOTH_SERVICES

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.switchbot.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(
    params=[
        SwitchbotModel.BOT,
        SwitchbotModel.CURTAIN,
        SwitchbotModel.METER,
        SwitchbotModel.METER_PRO_C,
        SwitchbotModel.LEAK,
        SwitchbotModel.REMOTE,
        SwitchbotModel.HUB2,
        SwitchbotModel.LOCK,
        SwitchbotModel.RELAY_SWITCH_1PM,
        SwitchbotModel.HUBMINI_MATTER,
        SwitchbotModel.BLIND_TILT,
        SwitchbotModel.ROLLER_SHADE,
        SwitchbotModel.HUMIDIFIER,
        SwitchbotModel.LIGHT_STRIP,
        SwitchbotModel.LOCK_PRO,
        SwitchbotModel.CIRCULATOR_FAN,
        SwitchbotModel.K20_VACUUM,
        SwitchbotModel.K10_PRO_VACUUM,
        SwitchbotModel.K10_VACUUM,
        SwitchbotModel.K10_PRO_COMBO_VACUUM,
        SwitchbotModel.S10_VACUUM,
    ]
)
async def switchbot_model(request: pytest.FixtureRequest) -> SwitchbotModel:
    """Return every device."""
    return SwitchbotModel(request.param)


@pytest.fixture
async def bluetooth_service_info(
    switchbot_model: SwitchbotModel,
) -> BluetoothServiceInfoBleak:
    """Return a BluetoothServiceInfoBleak object for the given Switchbot model."""
    return BLUETOOTH_SERVICES[switchbot_model]


@pytest.fixture
async def setup_service(
    hass: HomeAssistant,
    bluetooth_service_info: BluetoothServiceInfoBleak,
) -> None:
    """Set up the Switchbot service."""
    await async_setup_component(hass, "bluetooth", {})
    inject_bluetooth_service_info(hass, bluetooth_service_info)


@pytest.fixture
def mock_config_entry(
    switchbot_model: SwitchbotModel,
    encrypted_data: dict[str, Any],
    bluetooth_service_info: BluetoothServiceInfoBleak,
    setup_service: None,
    switchbot_device: None,
) -> MockConfigEntry:
    """Fixture to create a MockConfigEntry for a Switchbot device."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: bluetooth_service_info.address,
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: SUPPORTED_MODEL_TYPES[switchbot_model],
        }
        | encrypted_data,
        unique_id="aabbccddeeff",
    )


@pytest.fixture
def encrypted_data(switchbot_model: SwitchbotModel) -> dict[str, Any]:
    """Fixture to create encrypted data for Switchbot devices."""
    if switchbot_model in ENCRYPTED_MODELS:
        return {
            CONF_KEY_ID: "ff",
            CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
        }
    return {}


@pytest.fixture
async def switchbot_device(
    mock_switchbot_blind_tilt: AsyncMock,
    mock_switchbot_roller_shade: AsyncMock,
    mock_switchbot_light_strip: AsyncMock,
    mock_switchbot_fan: AsyncMock,
    mock_switchbot_vacuum: AsyncMock,
) -> None:
    """Fixture to create a mock Switchbot device."""


@pytest.fixture
async def mock_switchbot_blind_tilt() -> AsyncGenerator[dict[str, AsyncMock]]:
    """Fixture to create a mock Switchbot device."""
    with (
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotBlindTilt.open"
        ) as mock_open,
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotBlindTilt.close"
        ) as mock_close,
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotBlindTilt.stop"
        ) as mock_stop,
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotBlindTilt.set_position"
        ) as mock_set_position,
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotBlindTilt.get_basic_info"
        ) as mock_get_basic_info,
    ):
        mock_get_basic_info.return_value = {
            "motionDirection": {
                "opening": False,
                "closing": False,
                "up": False,
                "down": False,
            },
        }
        yield {
            "open": mock_open,
            "close": mock_close,
            "stop": mock_stop,
            "set_position": mock_set_position,
            "get_basic_info": mock_get_basic_info,
        }
    # with patch.multiple(
    #     "homeassistant.components.switchbot.cover.switchbot.SwitchbotBlindTilt",
    #     open=AsyncMock(),
    #     close=AsyncMock(),
    #     stop=AsyncMock(),
    #     set_position=AsyncMock(),
    #     get_basic_info=AsyncMock(),
    # ) as mock_blind_tilt:
    #     mock_blind_tilt.get_basic_info.return_value = {
    #         "motionDirection": {
    #             "opening": False,
    #             "closing": False,
    #             "up": False,
    #             "down": False,
    #         },
    #     }
    #     print(mock_blind_tilt)
    #     yield mock_blind_tilt


@pytest.fixture
async def mock_switchbot_roller_shade() -> AsyncGenerator[dict[str, AsyncMock]]:
    """Fixture to create a mock Switchbot device."""
    with (
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotRollerShade.update"
        ) as mock_update,
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotRollerShade.open"
        ) as mock_open,
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotRollerShade.close"
        ) as mock_close,
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotRollerShade.stop"
        ) as mock_stop,
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotRollerShade.set_position"
        ) as mock_set_position,
    ):
        yield {
            "update": mock_update,
            "open": mock_open,
            "close": mock_close,
            "stop": mock_stop,
            "set_position": mock_set_position,
        }


@pytest.fixture
async def mock_switchbot_humidifier() -> AsyncGenerator[dict[str, AsyncMock]]:
    """Fixture to create a mock Switchbot device."""
    with (
        patch(
            "homeassistant.components.switchbot.humidifier.switchbot.SwitchbotHumidifier.update"
        ) as mock_open,
        patch(
            "homeassistant.components.switchbot.humidifier.switchbot.SwitchbotHumidifier.set_level"
        ) as mock_set_level,
        patch(
            "homeassistant.components.switchbot.humidifier.switchbot.SwitchbotHumidifier.async_set_auto"
        ) as mock_set_auto,
        patch(
            "homeassistant.components.switchbot.humidifier.switchbot.SwitchbotHumidifier.async_set_manual"
        ) as mock_set_manual,
        patch(
            "homeassistant.components.switchbot.humidifier.switchbot.SwitchbotHumidifier.turn_off"
        ) as mock_turn_off,
        patch(
            "homeassistant.components.switchbot.humidifier.switchbot.SwitchbotHumidifier.turn_on"
        ) as mock_turn_on,
    ):
        yield {
            "open": mock_open,
            "set_level": mock_set_level,
            "set_auto": mock_set_auto,
            "set_manual": mock_set_manual,
            "turn_off": mock_turn_off,
            "turn_on": mock_turn_on,
        }


@pytest.fixture
async def mock_switchbot_light_strip() -> AsyncGenerator[AsyncMock]:
    """Fixture to create a mock Switchbot device."""
    with patch(
        "homeassistant.components.switchbot.fan.switchbot.SwitchbotLightStrip.update"
    ):
        yield


@pytest.fixture
async def mock_switchbot_fan() -> AsyncGenerator[AsyncMock]:
    """Fixture to create a mock Switchbot device."""
    with patch("homeassistant.components.switchbot.fan.switchbot.SwitchbotFan.update"):
        yield


@pytest.fixture
async def mock_switchbot_vacuum() -> AsyncGenerator[AsyncMock]:
    """Fixture to create a mock Switchbot device."""
    with patch(
        "homeassistant.components.switchbot.vacuum.switchbot.SwitchbotVacuum.update"
    ):
        yield


@pytest.fixture
async def mock_switchbot_curtain() -> AsyncGenerator[dict[str, AsyncMock]]:
    """Fixture to create a mock Switchbot device."""
    with (
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotCurtain.open"
        ) as mock_open,
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotCurtain.close"
        ) as mock_close,
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotCurtain.stop"
        ) as mock_stop,
        patch(
            "homeassistant.components.switchbot.cover.switchbot.SwitchbotCurtain.set_position"
        ) as mock_set_position,
    ):
        yield {
            "open": mock_open,
            "close": mock_close,
            "stop": mock_stop,
            "set_position": mock_set_position,
        }


@pytest.fixture
def mock_entry_factory():
    """Fixture to create a MockConfigEntry with a customizable sensor type."""
    return lambda sensor_type="curtain": MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: sensor_type,
        },
        unique_id="aabbccddeeff",
    )


@pytest.fixture
def mock_entry_encrypted_factory():
    """Fixture to create a MockConfigEntry with an encryption key and a customizable sensor type."""
    return lambda sensor_type="lock": MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: sensor_type,
            CONF_KEY_ID: "ff",
            CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
        },
        unique_id="aabbccddeeff",
    )
