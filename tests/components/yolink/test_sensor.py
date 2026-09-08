"""Tests for YoLink sensors."""

from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from yolink.client import YoLinkClient
from yolink.const import (
    ATTR_DEVICE_MULTI_CAPS_LEAK_SENSOR,
    ATTR_DEVICE_MULTI_FUNCTIONAL_SENSOR,
    ATTR_DEVICE_SOIL_TH_SENSOR,
    ATTR_DEVICE_TH_SENSOR,
    ATTR_DEVICE_WATER_METER_CONTROLLER,
)
from yolink.device import YoLinkDevice, YoLinkDeviceMode
from yolink.message_resolver import resolve_sub_message
from yolink.model import BRDP

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.yolink import DOMAIN, YoLinkHomeMessageListener
from homeassistant.components.yolink.const import (
    DEV_MODEL_WATER_METER_YS5018_EC,
    DEV_MODEL_WATER_METER_YS5018_UC,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


def _mock_device(
    *,
    device_id: str,
    device_name: str,
    device_type: str,
    device_model: str,
    state: dict[str, Any],
) -> YoLinkDevice:
    """Create a YoLink device with a mocked API response."""
    client = MagicMock(spec=YoLinkClient)
    client.execute = AsyncMock(
        return_value=BRDP(
            code="000000",
            desc="Success",
            data={"state": deepcopy(state)},
        )
    )
    return YoLinkDevice(
        YoLinkDeviceMode(
            deviceId=device_id,
            name=device_name,
            token="REDACTED",
            type=device_type,
            modelName=device_model,
        ),
        client,
    )


async def _async_setup_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yolink_home: MagicMock,
    devices: list[YoLinkDevice],
) -> None:
    """Set up YoLink with the supplied devices."""
    mock_yolink_home.return_value.get_devices.return_value = devices
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


def _assert_temperature_state(
    hass: HomeAssistant,
    entity_id: str,
    expected_temperature: float,
) -> None:
    """Assert a temperature sensor's public state and attributes."""
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == str(expected_temperature)
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT


@pytest.mark.usefixtures("setup_credentials", "mock_auth_manager")
@pytest.mark.parametrize(
    ("device_model", "device_id", "device_name"),
    [
        pytest.param(
            DEV_MODEL_WATER_METER_YS5018_UC,
            "water-meter-uc",
            "FlowSmart Water Meter UC",
            id="ys5018-uc",
        ),
        pytest.param(
            DEV_MODEL_WATER_METER_YS5018_EC,
            "water-meter-ec",
            "FlowSmart Water Meter EC",
            id="ys5018-ec",
        ),
    ],
)
async def test_water_meter_temperature(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_yolink_home: MagicMock,
    water_meter_report: dict[str, Any],
    device_model: str,
    device_id: str,
    device_name: str,
) -> None:
    """Test YS5018 water meters expose top-level water temperature."""
    device = _mock_device(
        device_id=device_id,
        device_name=device_name,
        device_type=ATTR_DEVICE_WATER_METER_CONTROLLER,
        device_model=device_model,
        state=water_meter_report["data"],
    )

    await _async_setup_devices(hass, mock_config_entry, mock_yolink_home, [device])

    entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{device_id} temperature"
    )
    assert entity_id is not None
    _assert_temperature_state(hass, entity_id, 17.7)


@pytest.mark.usefixtures("setup_credentials", "mock_auth_manager")
async def test_other_water_meter_has_no_temperature_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_yolink_home: MagicMock,
    water_meter_report: dict[str, Any],
) -> None:
    """Test another water meter model does not expose temperature."""
    device = _mock_device(
        device_id="other-water-meter",
        device_name="Other Water Meter",
        device_type=ATTR_DEVICE_WATER_METER_CONTROLLER,
        device_model="YS5008-UC",
        state=water_meter_report["data"],
    )

    await _async_setup_devices(hass, mock_config_entry, mock_yolink_home, [device])

    assert (
        entity_registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, "other-water-meter temperature"
        )
        is None
    )


@pytest.mark.usefixtures("setup_credentials", "mock_auth_manager")
@pytest.mark.parametrize(
    ("device_type", "state", "expected_temperature"),
    [
        pytest.param(
            ATTR_DEVICE_TH_SENSOR,
            {"temperature": 20.1},
            20.1,
            id="th-sensor",
        ),
        pytest.param(
            ATTR_DEVICE_SOIL_TH_SENSOR,
            {"state": {"temperature": 20.2}},
            20.2,
            id="soil-th-sensor",
        ),
        pytest.param(
            ATTR_DEVICE_MULTI_CAPS_LEAK_SENSOR,
            {"state": {"temperature": 20.3}},
            20.3,
            id="multi-caps-leak-sensor",
        ),
        pytest.param(
            ATTR_DEVICE_MULTI_FUNCTIONAL_SENSOR,
            {"state": {"temperature": 20.4}},
            20.4,
            id="multi-functional-sensor",
        ),
    ],
)
async def test_existing_temperature_devices(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_yolink_home: MagicMock,
    device_type: str,
    state: dict[str, Any],
    expected_temperature: float,
) -> None:
    """Test existing temperature-capable device types remain supported."""
    device = _mock_device(
        device_id="temperature-device",
        device_name="Temperature Device",
        device_type=device_type,
        device_model="YS9999-UC",
        state=state,
    )

    await _async_setup_devices(hass, mock_config_entry, mock_yolink_home, [device])

    entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, "temperature-device temperature"
    )
    assert entity_id is not None
    _assert_temperature_state(hass, entity_id, expected_temperature)


@pytest.mark.usefixtures("setup_credentials", "mock_auth_manager")
async def test_water_meter_temperature_retained_on_partial_report(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_yolink_home: MagicMock,
    water_meter_report: dict[str, Any],
) -> None:
    """Test a partial report does not clear the last water temperature."""
    device = _mock_device(
        device_id="water-meter-uc",
        device_name="FlowSmart Water Meter UC",
        device_type=ATTR_DEVICE_WATER_METER_CONTROLLER,
        device_model=DEV_MODEL_WATER_METER_YS5018_UC,
        state=water_meter_report["data"],
    )
    await _async_setup_devices(hass, mock_config_entry, mock_yolink_home, [device])
    entity_id = entity_registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, "water-meter-uc temperature"
    )
    assert entity_id is not None
    _assert_temperature_state(hass, entity_id, 17.7)

    partial_report = {
        "state": {
            "valve": "closed",
            "waterFlowing": False,
        }
    }
    resolve_sub_message(device, partial_report, "Report")
    setup_call = mock_yolink_home.return_value.async_setup.await_args
    assert setup_call is not None
    registered_listener = next(
        (
            argument
            for argument in (*setup_call.args, *setup_call.kwargs.values())
            if isinstance(argument, YoLinkHomeMessageListener)
        ),
        None,
    )
    assert isinstance(registered_listener, YoLinkHomeMessageListener)
    registered_listener.on_message(device, partial_report)
    await hass.async_block_till_done()

    _assert_temperature_state(hass, entity_id, 17.7)
