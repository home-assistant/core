"""Tests for the Place binary sensor platform."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from place.models.device_shadow import AlarmStatus
from place.models.discover_device import DiscoverDevice
import pytest

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import setup_integration, trigger_shadow_callback

from tests.common import MockConfigEntry


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_provider",
    "mock_get_iot_credentials",
    "mock_mqtt_client",
)
async def test_binary_sensor_entities_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that alarm binary sensor entities are created for each device."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("binary_sensor.master_bedroom_smoke") is not None
    assert hass.states.get("binary_sensor.master_bedroom_carbon_monoxide") is not None
    assert hass.states.get("binary_sensor.master_bedroom_heat_alarm") is not None


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_provider",
    "mock_get_iot_credentials",
)
@pytest.mark.parametrize(
    ("raw_value", "expected_state"),
    [
        pytest.param(0, STATE_OFF, id="idle"),
        pytest.param(1, STATE_OFF, id="test"),
        pytest.param(2, STATE_OFF, id="pre_alarm"),
        pytest.param(3, STATE_ON, id="alarm"),
        pytest.param(4, STATE_ON, id="critical_alarm"),
        pytest.param(5, STATE_OFF, id="hushed"),
        pytest.param(6, STATE_UNAVAILABLE, id="not_present"),
    ],
)
async def test_binary_sensor_alarm_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_client: MagicMock,
    raw_value: int,
    expected_state: str,
) -> None:
    """Test each AlarmStatus maps to the expected binary sensor state."""
    await setup_integration(hass, mock_config_entry)

    payload = json.dumps(
        {"state": {"reported": {"smokeAlarmStatus": raw_value}}}
    ).encode()
    trigger_shadow_callback(
        mock_mqtt_client,
        "$aws/things/thing-001/shadow/update/accepted",
        payload,
    )
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.master_bedroom_smoke").state == expected_state


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_get_iot_credentials",
)
async def test_binary_sensor_skip_absent_alarms(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that entities are not created for alarms absent from discovery.

    Garage units have heat alarms but not smoke alarms; verify entities are only
    created for supported alarm types.
    """
    garage_device = DiscoverDevice(
        location="Garage",
        shadow={
            "coAlarmStatus": int(AlarmStatus.IDLE),
            "heatAlarmStatus": int(AlarmStatus.IDLE),
            "smokeAlarmStatus": int(AlarmStatus.NOT_PRESENT),
            "temperatureC": 20.0,
            "humidity": 50,
            "batteryStatus": 0,
        },
        device_name="Garage Detector",
        thing_name="garage-001",
        firmware_version="1.0.0",
        model_number="GARAGE-MODEL",
        device_id="garage-device-001",
        online=True,
    )

    with patch(
        "homeassistant.components.gentex_place.Provider", autospec=True
    ) as mock_provider_cls:
        mock_provider_instance = mock_provider_cls.return_value
        mock_provider_instance.enable = AsyncMock()
        mock_provider_instance.discover = AsyncMock(return_value=[garage_device])

        with patch(
            "homeassistant.components.gentex_place.MqttClient", autospec=True
        ) as mock_mqtt_cls:
            mock_mqtt_instance = mock_mqtt_cls.return_value
            mock_mqtt_instance._client = MagicMock()

            await setup_integration(hass, mock_config_entry)

    # Smoke alarm should not be created for garage unit
    assert hass.states.get("binary_sensor.garage_smoke") is None
    # Heat and CO alarms should still be created
    assert hass.states.get("binary_sensor.garage_heat_alarm") is not None
    assert hass.states.get("binary_sensor.garage_carbon_monoxide") is not None


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_get_iot_credentials",
)
async def test_binary_sensor_skip_unknown_alarms(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that no entities are created when discovery has no shadow at all.

    Alarm support cannot be confirmed without a shadow, so no entities should
    be created until a shadow becomes available.
    """
    unknown_device = DiscoverDevice(
        location="Hallway",
        shadow={},
        device_name="Hallway Detector",
        thing_name="hallway-001",
        firmware_version="1.0.0",
        model_number="MODEL-X",
        device_id="hallway-device-001",
        online=True,
    )

    with patch(
        "homeassistant.components.gentex_place.Provider", autospec=True
    ) as mock_provider_cls:
        mock_provider_instance = mock_provider_cls.return_value
        mock_provider_instance.enable = AsyncMock()
        mock_provider_instance.discover = AsyncMock(return_value=[unknown_device])

        with patch(
            "homeassistant.components.gentex_place.MqttClient", autospec=True
        ) as mock_mqtt_cls:
            mock_mqtt_instance = mock_mqtt_cls.return_value
            mock_mqtt_instance._client = MagicMock()

            await setup_integration(hass, mock_config_entry)

    assert hass.states.get("binary_sensor.hallway_smoke") is None
    assert hass.states.get("binary_sensor.hallway_heat_alarm") is None
    assert hass.states.get("binary_sensor.hallway_carbon_monoxide") is None


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_get_iot_credentials",
)
async def test_binary_sensor_late_shadow_adds_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that an entity is added once a later shadow confirms alarm support.

    Discovery returned no shadow, so no entities were created at setup. Once
    the requested MQTT shadow arrives confirming a smoke alarm is present, the
    entity should be added without requiring a reload.
    """
    unknown_device = DiscoverDevice(
        location="Hallway",
        shadow={},
        device_name="Hallway Detector",
        thing_name="hallway-001",
        firmware_version="1.0.0",
        model_number="MODEL-X",
        device_id="hallway-device-001",
        online=True,
    )

    with patch(
        "homeassistant.components.gentex_place.Provider", autospec=True
    ) as mock_provider_cls:
        mock_provider_instance = mock_provider_cls.return_value
        mock_provider_instance.enable = AsyncMock()
        mock_provider_instance.discover = AsyncMock(return_value=[unknown_device])

        with patch(
            "homeassistant.components.gentex_place.MqttClient", autospec=True
        ) as mock_mqtt_cls:
            mock_mqtt_instance = mock_mqtt_cls.return_value
            mock_mqtt_instance._client = MagicMock()

            await setup_integration(hass, mock_config_entry)

            assert hass.states.get("binary_sensor.hallway_smoke") is None

            payload = json.dumps(
                {"state": {"reported": {"smokeAlarmStatus": int(AlarmStatus.IDLE)}}}
            ).encode()
            trigger_shadow_callback(
                mock_mqtt_instance,
                "$aws/things/hallway-001/shadow/update/accepted",
                payload,
            )
            await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.hallway_smoke").state == STATE_OFF
    # co/heat still absent — the payload didn't confirm them
    assert hass.states.get("binary_sensor.hallway_heat_alarm") is None
    assert hass.states.get("binary_sensor.hallway_carbon_monoxide") is None
