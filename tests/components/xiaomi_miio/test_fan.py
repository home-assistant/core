"""The tests for the xiaomi_miio fan component."""

from collections.abc import Generator
from unittest.mock import MagicMock, Mock, patch

from miio.integrations.fan.dmaker.fan import FanStatusP5
from miio.integrations.fan.dmaker.fan_miot import FanStatusMiot
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.xiaomi_miio import MODEL_TO_CLASS_MAP
from homeassistant.components.xiaomi_miio.const import CONF_FLOW_TYPE, DOMAIN
from homeassistant.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_TOKEN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import TEST_MAC

from tests.common import MockConfigEntry, snapshot_platform

_MODEL_INFORMATION = {
    "dmaker.fan.p5": {
        "patch_class": "homeassistant.components.xiaomi_miio.FanP5",
        "mock_status": FanStatusP5(
            {
                "roll_angle": 60,
                "beep_sound": False,
                "child_lock": False,
                "time_off": 0,
                "power": False,
                "light": True,
                "mode": "nature",
                "roll_enable": False,
                "speed": 64,
            }
        ),
    },
    "dmaker.fan.p18": {
        "patch_class": "homeassistant.components.xiaomi_miio.FanMiot",
        "mock_status": FanStatusMiot(
            {
                "swing_mode_angle": 90,
                "buzzer": False,
                "child_lock": False,
                "power_off_time": 0,
                "power": False,
                "light": True,
                "mode": 0,
                "swing_mode": False,
                "fan_speed": 100,
            }
        ),
    },
}


@pytest.fixture(
    name="model_code",
    params=_MODEL_INFORMATION.keys(),
)
def get_model_code(request: pytest.FixtureRequest) -> str:
    """Parametrize model code."""
    return request.param


@pytest.fixture(autouse=True)
def setup_device(model_code: str) -> Generator[MagicMock]:
    """Initialize test xiaomi_miio for fan entity."""

    model_information = _MODEL_INFORMATION[model_code]

    mock_fan = MagicMock()
    mock_fan.status = Mock(return_value=model_information["mock_status"])

    with (
        patch(
            "homeassistant.components.xiaomi_miio.get_platforms",
            return_value=[Platform.FAN],
        ),
        patch(model_information["patch_class"]) as mock_fan_cls,
        patch.dict(
            MODEL_TO_CLASS_MAP,
            {model_code: mock_fan_cls} if model_code in MODEL_TO_CLASS_MAP else {},
        ),
    ):
        mock_fan_cls.return_value = mock_fan
        yield mock_fan


async def setup_component(
    hass: HomeAssistant, model_code: str, entry_title: str
) -> MockConfigEntry:
    """Set up fan component."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="123456",
        title=entry_title,
        data={
            CONF_FLOW_TYPE: CONF_DEVICE,
            CONF_HOST: "192.168.1.100",
            CONF_TOKEN: "12345678901234567890123456789012",
            CONF_MODEL: model_code,
            CONF_MAC: TEST_MAC,
        },
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


async def test_fan_status(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    model_code: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test fan status."""

    config_entry = await setup_component(hass, model_code, "test_fan")
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)
