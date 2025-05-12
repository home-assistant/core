"""Define fixtures available for all tests."""

from collections.abc import Generator
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from switchbot import SwitchbotModel, SwitchbotDevice

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
        SwitchbotModel.S10_VACUUM
    ]
)
async def switchbot_model(
    hass: HomeAssistant, request: pytest.FixtureRequest
) -> SwitchbotModel:
    """Return every device."""
    model = SwitchbotModel(request.param)
    await async_setup_component(hass, "bluetooth", {})
    inject_bluetooth_service_info(hass, BLUETOOTH_SERVICES[model])
    return model


@pytest.fixture
def mock_config_entry(switchbot_model: SwitchbotModel, encrypted_data: dict[str, Any]) -> MockConfigEntry:
    """Fixture to create a MockConfigEntry for a Switchbot device."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: BLUETOOTH_SERVICES[switchbot_model].address,
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: SUPPORTED_MODEL_TYPES[switchbot_model],
        } | encrypted_data,
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
async def switchbot_device() -> AsyncGenerator[AsyncMock]:
    """Fixture to create a mock Switchbot device."""
    # device = AsyncMock(spec=SwitchbotDevice, autospec=True)
    with (
        # patch("homeassistant.components.switchbot.coordinator.switchbot.SwitchbotDevice", new=device),
        # patch("switchbot.SwitchbotVacuum"),
        # patch("switchbot.devices.vacuum.SwitchbotVacuum"),
        # patch("switchbot.SwitchbotFan"),
        patch("switchbot.SwitchbotBlindTilt", AsyncMock()),
        patch("switchbot.devices.blind_tilt.SwitchbotBlindTilt", AsyncMock()),
        # patch("homeassistant.components.switchbot.switchbot.SwitchbotBlindTilt", new=AsyncMock()),
        # patch("homeassistant.components.switchbot.switchbot.Switchbot", new=device),
        # patch("homeassistant.components.switchbot.switchbot.SwitchbotPlugMini", new=device),
        # patch("homeassistant.components.switchbot.switchbot.SwitchbotBulb", new=device),
        # patch("homeassistant.components.switchbot.switchbot.SwitchbotLightStrip", new=device),
        # patch("homeassistant.components.switchbot.switchbot.SwitchbotHumidifier", new=device),
        # patch("homeassistant.components.switchbot.switchbot.SwitchbotLock", new=device),
        # patch("homeassistant.components.switchbot.switchbot.SwitchbotBlindTilt", new=device),
        # patch("homeassistant.components.switchbot.switchbot.SwitchbotRelaySwitch", new=device),
        # patch("homeassistant.components.switchbot.switchbot.SwitchbotRollerShade", new=device),
        # patch("homeassistant.components.switchbot.switchbot.SwitchbotFan", device),
        # patch("homeassistant.components.switchbot.switchbot.SwitchbotVacuum", new=device),
          ):
        # device.update = AsyncMock()
        yield

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
