"""The tests for the xiaomi_miio humidifier component."""

from collections.abc import Generator
from unittest.mock import MagicMock, Mock, patch

from miio.integrations.humidifier.deerma.airhumidifier_jsqs import (
    AirHumidifierJsqsStatus,
)
from miio.integrations.humidifier.deerma.airhumidifier_mjjsq import (
    AirHumidifierStatus as AirHumidifierMjjsqStatus,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.humidifier import (
    ATTR_HUMIDITY,
    DOMAIN as HUMIDIFIER_DOMAIN,
    SERVICE_SET_HUMIDITY,
)
from homeassistant.components.xiaomi_miio import MODEL_TO_CLASS_MAP
from homeassistant.components.xiaomi_miio.const import CONF_FLOW_TYPE, DOMAIN
from homeassistant.components.xiaomi_miio.humidifier import (
    AirhumidifierMjjsqOperationMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
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

MODEL_AIRHUMIDIFIER_JSQ = "deerma.humidifier.jsq"
MODEL_AIRHUMIDIFIER_JSQ1 = "deerma.humidifier.jsq1"
MODEL_AIRHUMIDIFIER_MJJSQ = "deerma.humidifier.mjjsq"
MODEL_AIRHUMIDIFIER_CA4 = "zhimi.humidifier.ca4"
MODEL_AIRHUMIDIFIER_V1 = "zhimi.humidifier.v1"
MODEL_AIRHUMIDIFIER_CA1 = "zhimi.humidifier.ca1"

_MODEL_INFORMATION = {
    MODEL_AIRHUMIDIFIER_JSQ: {
        "patch_class": "homeassistant.components.xiaomi_miio.AirHumidifierMjjsq",
        "mock_status": AirHumidifierMjjsqStatus(
            {
                "OnOff_State": 0,
                "TemperatureValue": 22,
                "Humidity_Value": 45,
                "HumiSet_Value": 55,
                "Humidifier_Gear": 1,
                "Led_State": 1,
                "TipSound_State": 0,
                "waterstatus": 1,
                "watertankstatus": 1,
            }
        ),
    },
    MODEL_AIRHUMIDIFIER_JSQ1: {
        "patch_class": "homeassistant.components.xiaomi_miio.AirHumidifierMjjsq",
        "mock_status": AirHumidifierMjjsqStatus(
            {
                "OnOff_State": 0,
                "TemperatureValue": 22,
                "Humidity_Value": 45,
                "HumiSet_Value": 55,
                "Humidifier_Gear": 1,
                "Led_State": 1,
                "TipSound_State": 0,
                "waterstatus": 1,
                "watertankstatus": 1,
            }
        ),
    },
    MODEL_AIRHUMIDIFIER_MJJSQ: {
        "patch_class": "homeassistant.components.xiaomi_miio.AirHumidifierMjjsq",
        "mock_status": AirHumidifierMjjsqStatus(
            {
                "OnOff_State": 0,
                "TemperatureValue": 22,
                "Humidity_Value": 45,
                "HumiSet_Value": 55,
                "Humidifier_Gear": 1,
                "Led_State": 1,
                "TipSound_State": 0,
                "waterstatus": 1,
                "watertankstatus": 1,
            }
        ),
    },
    MODEL_AIRHUMIDIFIER_CA4: {
        "patch_class": "homeassistant.components.xiaomi_miio.AirHumidifierMiot",
        "mock_status": type(
            "ZhimiMiotStatus",
            (),
            {"is_on": False, "mode": 0, "humidity": 45, "target_humidity": 55},
        )(),
    },
    MODEL_AIRHUMIDIFIER_V1: {
        "patch_class": "homeassistant.components.xiaomi_miio.AirHumidifier",
        "mock_status": type(
            "ZhimiHumidifierStatus",
            (),
            {"is_on": False, "mode": "silent", "humidity": 45, "target_humidity": 55},
        )(),
    },
    MODEL_AIRHUMIDIFIER_CA1: {
        "patch_class": "homeassistant.components.xiaomi_miio.AirHumidifier",
        "mock_status": type(
            "ZhimiHumidifierStatus",
            (),
            {"is_on": False, "mode": "silent", "humidity": 45, "target_humidity": 55},
        )(),
    },
    "deerma.humidifier.jsq2w": {
        "patch_class": "homeassistant.components.xiaomi_miio.AirHumidifierJsqs",
        "mock_status": AirHumidifierJsqsStatus(
            {
                "power": False,
                "mode": 0,
                "humidity": 45,
                "target_humidity": 55,
                "led": True,
                "buzzer": False,
                "tank_filed": True,
            }
        ),
    },
    "deerma.humidifier.jsq3": {
        "patch_class": "homeassistant.components.xiaomi_miio.AirHumidifierJsqs",
        "mock_status": AirHumidifierJsqsStatus(
            {
                "power": False,
                "mode": 0,
                "humidity": 45,
                "target_humidity": 55,
                "led": True,
                "buzzer": False,
                "tank_filed": True,
            }
        ),
    },
    "deerma.humidifier.jsq5": {
        "patch_class": "homeassistant.components.xiaomi_miio.AirHumidifierJsqs",
        "mock_status": AirHumidifierJsqsStatus(
            {
                "power": False,
                "mode": 0,
                "humidity": 45,
                "target_humidity": 55,
                "led": True,
                "buzzer": False,
                "tank_filed": True,
            }
        ),
    },
    "deerma.humidifier.jsqs": {
        "patch_class": "homeassistant.components.xiaomi_miio.AirHumidifierJsqs",
        "mock_status": AirHumidifierJsqsStatus(
            {
                "power": False,
                "mode": 0,
                "humidity": 45,
                "target_humidity": 55,
                "led": True,
                "buzzer": False,
                "tank_filed": True,
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
    """Initialize test xiaomi_miio for humidifier entity."""

    model_information = _MODEL_INFORMATION[model_code]

    mock_humidifier = MagicMock()
    mock_humidifier.status = Mock(return_value=model_information["mock_status"])

    mock_humidifier.set_target_humidity.return_value = True
    mock_humidifier.set_mode.return_value = True

    with (
        patch(
            "homeassistant.components.xiaomi_miio.get_platforms",
            return_value=[Platform.HUMIDIFIER],
        ),
        patch(model_information["patch_class"]) as mock_humidifier_cls,
        patch.dict(
            MODEL_TO_CLASS_MAP,
            {model_code: mock_humidifier_cls}
            if model_code in MODEL_TO_CLASS_MAP
            else {},
        ),
    ):
        mock_humidifier_cls.return_value = mock_humidifier
        yield mock_humidifier


async def setup_component(
    hass: HomeAssistant, model_code: str, entry_title: str
) -> MockConfigEntry:
    """Set up humidifier component."""
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


async def test_humidifier_status(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    model_code: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test humidifier status."""

    config_entry = await setup_component(hass, model_code, "test_humidifier")
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)

    entity_state = hass.states.get("humidifier.test_humidifier")
    assert entity_state is not None


async def test_humidifier_set_humidity(
    hass: HomeAssistant,
    model_code: str,
    setup_device: MagicMock,
) -> None:
    """Test setting target humidity and forcing mode change."""

    await setup_component(hass, model_code, "test_humidifier")

    await hass.services.async_call(
        HUMIDIFIER_DOMAIN,
        SERVICE_SET_HUMIDITY,
        {
            ATTR_ENTITY_ID: "humidifier.test_humidifier",
            ATTR_HUMIDITY: 50,
        },
        blocking=True,
    )

    setup_device.set_target_humidity.assert_called_once()

    if model_code == MODEL_AIRHUMIDIFIER_MJJSQ:
        setup_device.set_mode.assert_called_once_with(
            AirhumidifierMjjsqOperationMode.Humidity
        )
