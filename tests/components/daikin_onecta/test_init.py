"""Test daikin_onecta sensor."""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from daikin_onecta import GatewayDevice
from daikin_onecta.models import Characteristic, FanSpeed, Schedule
import pytest
from yarl import URL

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_HORIZONTAL_MODE,
    ATTR_SWING_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_MIDDLE,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_NONE,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_HORIZONTAL_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    HVACMode,
)
from homeassistant.components.daikin_onecta import update_listener
from homeassistant.components.daikin_onecta.climate import DaikinClimate
from homeassistant.components.daikin_onecta.const import (
    CONF_HOMEKIT_FAN_MODE_ALIASES,
    DAIKIN_API_URL,
    DOMAIN,
    SCHEDULE_OFF,
)
from homeassistant.components.daikin_onecta.device import (
    DaikinOnectaDevice,
    migrate_legacy_entity_unique_ids,
    migrate_legacy_subdevice_identifiers,
)
from homeassistant.components.daikin_onecta.diagnostics import (
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)
from homeassistant.components.daikin_onecta.entity import DaikinSwitch
from homeassistant.components.daikin_onecta.select import DaikinScheduleSelect
from homeassistant.components.daikin_onecta.sensor import (
    migrate_legacy_sensor_unique_ids,
)
from homeassistant.components.daikin_onecta.system_health import (
    async_register,
    system_health_info,
)
from homeassistant.components.daikin_onecta.update import (
    DaikinFirmwareUpdateEntity,
    migrate_legacy_update_unique_ids,
)
from homeassistant.components.daikin_onecta.water_heater import DaikinWaterTank
from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN, SERVICE_INSTALL
from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE,
    STATE_HEAT_PUMP,
    STATE_PERFORMANCE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr
import homeassistant.helpers.entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import (
    FAKE_ACCESS_TOKEN,
    SnapshotTestContext,
    load_fixture_json,
    snapshot_platform_entities,
)

from tests.common import MockConfigEntry


def _assert_initial_climate_state(hass: HomeAssistant) -> None:
    """Assert the baseline entities exposed by the climate fixture."""
    assert hass.states.get("climate.werkkamer_room_temperature").state == HVACMode.OFF
    assert (
        hass.states.get(
            "binary_sensor.werkkamer_climatecontrol_is_cool_heat_master"
        ).state
        == STATE_ON
    )
    assert (
        hass.states.get(
            "binary_sensor.werkkamer_climatecontrol_is_in_caution_state"
        ).state
        == STATE_OFF
    )
    assert (
        hass.states.get(
            "binary_sensor.werkkamer_climatecontrol_is_in_warning_state"
        ).state
        == STATE_OFF
    )


EXPECTED_INITIAL_CLIMATE_CALLS = 3
EXPECTED_DRY_MODE_CALLS = 4
EXPECTED_COOL_MODE_CALLS = 5
EXPECTED_HEAT_MODE_CALLS = 6
EXPECTED_FINAL_DRY_MODE_CALLS = 7
EXPECTED_TANK_TEMPERATURE = 58
EXPECTED_TANK_CALLS_AFTER_TEMPERATURE = 2
EXPECTED_TANK_CALLS_AFTER_OFF = 3
EXPECTED_TANK_CALLS_AFTER_PERFORMANCE = 5
EXPECTED_TANK_CALLS_AFTER_HEAT_PUMP = 6
EXPECTED_TANK_CALLS_AFTER_SECOND_OFF = 7
EXPECTED_TANK_CALLS_AFTER_SECOND_ON = 8
EXPECTED_TANK_CALLS_AFTER_TURN_OFF = 9
EXPECTED_TANK_CALLS_AFTER_TURN_ON = 10
EXPECTED_REMAINING_MINUTE_RATE_LIMIT = 4
EXPECTED_REMAINING_DAY_RATE_LIMIT = 10
EXPECTED_FAILED_TANK_WRITE_CALLS = 1
EXPECTED_LEAVING_WATER_OFFSET_MINIMUM = -10
EXPECTED_LEAVING_WATER_OFFSET_MAXIMUM = 10
EXPECTED_LEAVING_WATER_OFFSET_CURRENT_TEMPERATURE = 25
EXPECTED_FLOOR_HEATING_CURRENT_TEMPERATURE = 25
EXPECTED_FLOOR_HEATING_OFFSET_TEMPERATURE = -3
EXPECTED_CLIMATE_CALLS_AFTER_FIRST_ON = 2
EXPECTED_CLIMATE_CALLS_AFTER_FIRST_OFF = 3
EXPECTED_CLIMATE_CALLS_AFTER_COOL = 4
EXPECTED_CLIMATE_CALLS_AFTER_HEAT = 5
EXPECTED_CLIMATE_CALLS_AFTER_HVAC_OFF = 6
EXPECTED_CLIMATE_CALLS_AFTER_HEAT_ON = 7
EXPECTED_CLIMATE_CALLS_AFTER_FIXED_FAN = 9
EXPECTED_CLIMATE_CALLS_AFTER_FAN_SPEED = 10
EXPECTED_CLIMATE_CALLS_AFTER_AUTO_FAN = 11
EXPECTED_CLIMATE_CALLS_AFTER_TEMPERATURE = 12
EXPECTED_CLIMATE_TARGET_TEMPERATURE = 25
EXPECTED_CLIMATE_CALLS_AFTER_COOL_TEMPERATURE = 14
EXPECTED_COOL_TARGET_TEMPERATURE = 20
EXPECTED_CLIMATE_CALLS_AFTER_SWING = 16
EXPECTED_CLIMATE_CALLS_AFTER_BOOST = 17
EXPECTED_CLIMATE_CALLS_AFTER_BOOST_OFF = 18
EXPECTED_CLIMATE_CALLS_AFTER_SECOND_HVAC_OFF = 19
EXPECTED_CLIMATE_CALLS_AFTER_BOOST_POWER_ON = 21
EXPECTED_CLIMATE_CALLS_AFTER_STREAMER_ON = 22
EXPECTED_CLIMATE_CALLS_AFTER_STREAMER_OFF = 23
EXPECTED_CLIMATE_CALLS_AFTER_AWAY = 25
EXPECTED_CLIMATE_CALLS_AFTER_AWAY_OFF = 26
EXPECTED_CLIMATE_CALLS_AFTER_SCHEDULE_ON = 27
EXPECTED_CLIMATE_CALLS_AFTER_SCHEDULE_OFF = 28
EXPECTED_CLIMATE_CALLS_AFTER_CUSTOM_SCHEDULE_ON = 29
EXPECTED_CLIMATE_CALLS_AFTER_CUSTOM_SCHEDULE_OFF = 30
EXPECTED_CLIMATE_CALLS_AFTER_FINAL_OFF = 31
EXPECTED_CLIMATE_CALLS_AFTER_DRY = 33
EXPECTED_CLIMATE_CALLS_AFTER_UPDATE = 34
EXPECTED_CLIMATE_CALLS_AFTER_SWING_ALIAS = 35
EXPECTED_CLIMATE_WRITE_CALLS = 2
EXPECTED_MINIMAL_DATA_WATER_TEMPERATURE = 53
EXPECTED_GAS_ROOM_TEMPERATURE = 25
EXPECTED_BUTTON_WRITE_CALLS = 2
EXPECTED_FIRMWARE_WRITE_CALLS = 2


@pytest.mark.asyncio
async def test_homehub(
    onecta_auth: AsyncMock,
    snapshot_context: SnapshotTestContext,
) -> None:
    """Test entities."""
    await snapshot_platform_entities(snapshot_context, Platform.SENSOR, "homehub")

    info = await system_health_info(snapshot_context.hass)

    assert info["max_minute"] == 0


@pytest.mark.asyncio
async def test_offlinedevice(
    onecta_auth: AsyncMock,
    snapshot_context: SnapshotTestContext,
) -> None:
    """Test entities."""
    await snapshot_platform_entities(snapshot_context, Platform.SENSOR, "offlinedevice")


@pytest.mark.asyncio
async def test_dry(
    onecta_auth: AsyncMock,
    snapshot_context: SnapshotTestContext,
) -> None:
    """Test entities."""
    hass = snapshot_context.hass
    await snapshot_platform_entities(snapshot_context, Platform.SENSOR, "dry")

    assert hass.states.get("climate.lounge_room_temperature").state == HVACMode.DRY
    assert (
        hass.states.get("update.lounge_gateway_firmware_update").attributes[
            "in_progress"
        ]
        is False
    )
    assert (
        hass.states.get("update.lounge_gateway_firmware_update").attributes[
            "installed_version"
        ]
        == "1_30_0"
    )
    assert (
        hass.states.get("update.lounge_gateway_firmware_update").attributes[
            "latest_version"
        ]
        == "1_30_0"
    )


@pytest.mark.asyncio
async def test_fanmode(
    onecta_auth: AsyncMock,
    snapshot_context: SnapshotTestContext,
) -> None:
    """Test entities."""
    hass = snapshot_context.hass
    aioclient_mock = snapshot_context.aioclient_mock
    await snapshot_platform_entities(snapshot_context, Platform.SENSOR, "fanmode")

    with patch(
        "homeassistant.components.daikin_onecta.DaikinApi.async_get_access_token",
        return_value=FAKE_ACCESS_TOKEN,
    ):
        assert hass.states.get("climate.Sala_room_temperature").state == HVACMode.OFF
        assert (
            hass.states.get("climate.Sala_room_temperature").attributes["fan_mode"]
            == "auto"
        )

        aioclient_mock.patch(
            DAIKIN_API_URL
            + "/v1/gateway-devices/13995b32-fc6e-43ed-918e-5d2b01095ccb/management-points/climateControl/characteristics/onOffMode",
            status=204,
        )
        aioclient_mock.patch(
            DAIKIN_API_URL
            + "/v1/gateway-devices/13995b32-fc6e-43ed-918e-5d2b01095ccb/management-points/climateControl/characteristics/operationMode",
            status=204,
        )

        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.Sala_room_temperature",
                ATTR_HVAC_MODE: HVACMode.COOL,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        assert len(aioclient_mock.mock_calls) == EXPECTED_INITIAL_CLIMATE_CALLS

        assert hass.states.get("climate.Sala_room_temperature").state == HVACMode.COOL
        assert (
            hass.states.get("climate.Sala_room_temperature").attributes["fan_mode"]
            == "3"
        )

        aioclient_mock.patch(
            DAIKIN_API_URL
            + "/v1/gateway-devices/13995b32-fc6e-43ed-918e-5d2b01095ccb/management-points/climateControl/characteristics/operationMode",
            status=204,
        )

        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.Sala_room_temperature",
                ATTR_HVAC_MODE: HVACMode.DRY,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        assert len(aioclient_mock.mock_calls) == EXPECTED_DRY_MODE_CALLS

        assert hass.states.get("climate.Sala_room_temperature").state == HVACMode.DRY
        assert (
            hass.states.get("climate.Sala_room_temperature").attributes["fan_mode"]
            == "auto"
        )

        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.Sala_room_temperature",
                ATTR_HVAC_MODE: HVACMode.COOL,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        assert len(aioclient_mock.mock_calls) == EXPECTED_COOL_MODE_CALLS

        assert hass.states.get("climate.Sala_room_temperature").state == HVACMode.COOL
        assert (
            hass.states.get("climate.Sala_room_temperature").attributes["fan_mode"]
            == "3"
        )

        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.Sala_room_temperature",
                ATTR_HVAC_MODE: HVACMode.HEAT,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        assert len(aioclient_mock.mock_calls) == EXPECTED_HEAT_MODE_CALLS

        assert hass.states.get("climate.Sala_room_temperature").state == HVACMode.HEAT
        assert (
            hass.states.get("climate.Sala_room_temperature").attributes["fan_mode"]
            == "auto"
        )

        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.Sala_room_temperature",
                ATTR_HVAC_MODE: HVACMode.DRY,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        assert len(aioclient_mock.mock_calls) == EXPECTED_FINAL_DRY_MODE_CALLS

        assert hass.states.get("climate.Sala_room_temperature").state == HVACMode.DRY
        assert (
            hass.states.get("climate.Sala_room_temperature").attributes["fan_mode"]
            == "auto"
        )


@pytest.mark.asyncio
async def test_dry2(
    onecta_auth: AsyncMock,
    snapshot_context: SnapshotTestContext,
) -> None:
    """Test entities."""
    await snapshot_platform_entities(snapshot_context, Platform.SENSOR, "dry2")

    assert (
        snapshot_context.hass.states.get("climate.bedroom_3_room_temperature").state
        == HVACMode.OFF
    )


@pytest.mark.asyncio
async def test_schedule(
    onecta_auth: AsyncMock,
    snapshot_context: SnapshotTestContext,
) -> None:
    """Test entities."""
    await snapshot_platform_entities(snapshot_context, Platform.SENSOR, "schedule")

    assert (
        snapshot_context.hass.states.get("select.master_climatecontrol_schedule").state
        == "off"
    )


@pytest.mark.asyncio
async def test_ururu(
    onecta_auth: AsyncMock,
    snapshot_context: SnapshotTestContext,
) -> None:
    """Test entities."""
    await snapshot_platform_entities(snapshot_context, Platform.SENSOR, "ururu")

    assert (
        snapshot_context.hass.states.get("climate.daikinap95800_room_temperature").state
        == HVACMode.HEAT
    )


@pytest.mark.asyncio
async def test_altherma(
    onecta_auth: AsyncMock,
    snapshot_context: SnapshotTestContext,
) -> None:
    """Test entities."""
    await snapshot_platform_entities(snapshot_context, Platform.SENSOR, "altherma")

    await snapshot_context.hass.async_block_till_done()

    assert (
        snapshot_context.hass.states.get(
            "sensor.altherma_climatecontrol_room_temperature"
        ).state
        == "21"
    )
    assert (
        snapshot_context.hass.states.get(
            "sensor.altherma_climatecontrol_heating_yearly_electrical_consumption"
        ).state
        == "1252"
    )

    sensor_entries = [
        entry
        for entry in er.async_entries_for_config_entry(
            snapshot_context.entity_registry, snapshot_context.config_entry.entry_id
        )
        if entry.entity_id.startswith("sensor.")
    ]
    assert len(sensor_entries) == len({entry.unique_id for entry in sensor_entries})


@pytest.mark.asyncio
async def test_altherma3m(
    onecta_auth: AsyncMock,
    snapshot_context: SnapshotTestContext,
) -> None:
    """Test entities."""
    await snapshot_platform_entities(snapshot_context, Platform.SENSOR, "altherma3m")

    assert (
        snapshot_context.hass.states.get(
            "climate.altherma_leaving_water_offset"
        ).attributes["min_temp"]
        == EXPECTED_LEAVING_WATER_OFFSET_MINIMUM
    )
    assert (
        snapshot_context.hass.states.get(
            "climate.altherma_leaving_water_offset"
        ).attributes["max_temp"]
        == EXPECTED_LEAVING_WATER_OFFSET_MAXIMUM
    )
    assert (
        snapshot_context.hass.states.get(
            "climate.altherma_leaving_water_offset"
        ).attributes["current_temperature"]
        == EXPECTED_LEAVING_WATER_OFFSET_CURRENT_TEMPERATURE
    )
    assert (
        snapshot_context.hass.states.get(
            "climate.altherma_leaving_water_offset"
        ).attributes["temperature"]
        == 0
    )


@pytest.mark.asyncio
async def test_altherma_ratelimit(
    onecta_auth: AsyncMock,
    snapshot_context: SnapshotTestContext,
) -> None:
    """Test entities."""
    hass = snapshot_context.hass
    config_entry = snapshot_context.config_entry
    aioclient_mock = snapshot_context.aioclient_mock
    await snapshot_platform_entities(snapshot_context, Platform.SENSOR, "altherma")

    patch_url = (
        DAIKIN_API_URL + "/v1/gateway-devices/1ece521b-5401-4a42-acce-6f76fba246aa/"
        "management-points/domesticHotWaterTank/characteristics/temperatureControl"
    )

    with patch(
        "homeassistant.components.daikin_onecta.DaikinApi.async_get_access_token",
        return_value="XXXXXX",
    ):
        aioclient_mock.patch(
            patch_url,
            status=429,
            headers={"X-RateLimit-Limit-minute": "0", "X-RateLimit-Limit-day": "0"},
        )

        temp = hass.states.get("water_heater.altherma").attributes["temperature"]

        info = await system_health_info(hass)

        assert info["max_minute"] == 0
        assert info["max_day"] == 0

        # Set the tank temperature to 58, but this should fail because of a rate limit
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: "water_heater.altherma", ATTR_TEMPERATURE: 58},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_TANK_CALLS_AFTER_TEMPERATURE

        assert aioclient_mock.mock_calls[1][2] == {
            "value": 58,
            "path": "/operationModes/heating/setpoints/domesticHotWaterTemperature",
        }
        assert (
            hass.states.get("water_heater.altherma").attributes["temperature"] == temp
        )

        aioclient_mock.get(DAIKIN_API_URL + "/v1/gateway-devices", status=429)

        # Test that updating the data through with a 429 doesn't crash
        coordinator = config_entry.runtime_data
        await coordinator.async_update_data()

        aioclient_mock.get(
            DAIKIN_API_URL + "/v1/gateway-devices",
            status=200,
            json=load_fixture_json("altherma"),
        )

        # Test that updating the data through with a status 200 works
        coordinator = config_entry.runtime_data
        await coordinator.async_update_data()


@pytest.mark.asyncio
async def test_climate_fixedfanmode(
    onecta_auth: AsyncMock,
    snapshot_context: SnapshotTestContext,
) -> None:
    """Test entities."""
    hass = snapshot_context.hass
    await snapshot_platform_entities(
        snapshot_context, Platform.SENSOR, "climate_fixedfanmode"
    )

    assert (
        hass.states.get("climate.werkkamer_room_temperature").attributes["fan_mode"]
        == "3"
    )
    fan_modes = hass.states.get("climate.werkkamer_room_temperature").attributes[
        "fan_modes"
    ]
    assert FAN_LOW not in fan_modes
    assert FAN_MIDDLE not in fan_modes
    assert FAN_MEDIUM not in fan_modes
    assert FAN_HIGH not in fan_modes


@pytest.mark.asyncio
async def test_climate_homekit_fan_mode_aliases(
    onecta_auth: AsyncMock,
    snapshot_context: SnapshotTestContext,
) -> None:
    """Test HomeKit fan mode aliases."""
    hass = snapshot_context.hass
    config_entry = snapshot_context.config_entry
    aioclient_mock = snapshot_context.aioclient_mock
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_HOMEKIT_FAN_MODE_ALIASES: True}
    )

    await snapshot_platform_entities(
        snapshot_context, Platform.SENSOR, "climate_fixedfanmode"
    )

    state = hass.states.get("climate.werkkamer_room_temperature")
    assert state.attributes["fan_mode"] == FAN_MEDIUM
    assert state.attributes["fan_modes"] == [
        "auto",
        "quiet",
        "1",
        "2",
        "3",
        "4",
        "5",
        FAN_LOW,
        FAN_MIDDLE,
        FAN_MEDIUM,
        FAN_HIGH,
    ]

    with patch(
        "homeassistant.components.daikin_onecta.DaikinApi.async_get_access_token",
        return_value="XXXXXX",
    ):
        aioclient_mock.patch(
            DAIKIN_API_URL
            + "/v1/gateway-devices/6f944461-08cb-4fee-979c-710ff66cea77/management-points/climateControl/characteristics/fanControl",
            status=204,
        )

        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_FAN_MODE: FAN_LOW,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert aioclient_mock.mock_calls[-1][2] == {
            "value": "quiet",
            "path": "/operationModes/heating/fanSpeed/currentMode",
        }
        assert (
            hass.states.get("climate.werkkamer_room_temperature").attributes["fan_mode"]
            == FAN_LOW
        )

        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_FAN_MODE: FAN_MIDDLE,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert aioclient_mock.mock_calls[-2][2] == {
            "value": "fixed",
            "path": "/operationModes/heating/fanSpeed/currentMode",
        }
        assert aioclient_mock.mock_calls[-1][2] == {
            "value": 2,
            "path": "/operationModes/heating/fanSpeed/modes/fixed",
        }
        assert (
            hass.states.get("climate.werkkamer_room_temperature").attributes["fan_mode"]
            == FAN_MIDDLE
        )

        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_FAN_MODE: FAN_HIGH,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert aioclient_mock.mock_calls[-1][2] == {
            "value": 5,
            "path": "/operationModes/heating/fanSpeed/modes/fixed",
        }
        assert (
            hass.states.get("climate.werkkamer_room_temperature").attributes["fan_mode"]
            == FAN_HIGH
        )

        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: "climate.werkkamer_room_temperature", ATTR_FAN_MODE: 3},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert aioclient_mock.mock_calls[-1][2] == {
            "value": 3,
            "path": "/operationModes/heating/fanSpeed/modes/fixed",
        }
    assert (
        hass.states.get("climate.werkkamer_room_temperature").attributes["fan_mode"]
        == "3"
    )


async def test_update_listener_notifies_entities() -> None:
    """Test options updates notify coordinator listeners."""
    coordinator = MagicMock()
    config_entry = MagicMock()
    config_entry.runtime_data = coordinator

    await update_listener(None, config_entry)

    coordinator.update_settings.assert_called_once_with(config_entry)
    coordinator.async_update_listeners.assert_called_once_with()


def test_homekit_fan_mode_alias_helpers() -> None:
    """Test HomeKit fan mode alias helper edge cases."""
    climate = DaikinClimate.__new__(DaikinClimate)
    climate.coordinator = MagicMock(options={CONF_HOMEKIT_FAN_MODE_ALIASES: True})

    assert climate.homekit_fan_mode_aliases(
        FanSpeed.from_dict(
            {"currentMode": {"value": "auto", "values": ["quiet", "auto"]}}
        )
    ) == {FAN_LOW: "quiet"}

    assert climate.homekit_fan_mode_aliases(
        FanSpeed.from_dict(
            {
                "currentMode": {
                    "value": "auto",
                    "values": ["quiet", "auto", "fixed"],
                },
                "modes": {},
            }
        )
    ) == {FAN_LOW: "quiet"}

    fan_speed = FanSpeed.from_dict(
        {
            "currentMode": {
                "value": "fixed",
                "values": ["quiet", "auto", "fixed"],
            },
            "modes": {
                "fixed": {
                    "value": 4,
                    "minValue": 1,
                    "maxValue": 5,
                    "stepValue": 1,
                },
            },
        }
    )
    assert climate.get_homekit_fan_mode(fan_speed, "4") == "4"
    assert climate.resolve_homekit_fan_mode_alias(fan_speed, FAN_HIGH) == "5"


@pytest.mark.asyncio
async def test_climate_floorheatingairflow(
    onecta_auth: AsyncMock,
    snapshot_context: SnapshotTestContext,
) -> None:
    """Test entities."""
    await snapshot_platform_entities(
        snapshot_context, Platform.SENSOR, "climate_floorheatingairflow"
    )


@pytest.mark.asyncio
async def test_mc80z(
    onecta_auth: AsyncMock,
    snapshot_context: SnapshotTestContext,
) -> None:
    """Test entities."""
    await snapshot_platform_entities(snapshot_context, Platform.SENSOR, "mc80z")

    assert (
        snapshot_context.hass.states.get(
            "climate.vloerverwarming_leaving_water_offset"
        ).attributes["current_temperature"]
        == EXPECTED_FLOOR_HEATING_CURRENT_TEMPERATURE
    )
    assert (
        snapshot_context.hass.states.get(
            "climate.vloerverwarming_leaving_water_offset"
        ).attributes["temperature"]
        == EXPECTED_FLOOR_HEATING_OFFSET_TEMPERATURE
    )


@pytest.mark.asyncio
async def test_holidaymode(
    onecta_auth: AsyncMock,
    snapshot_context: SnapshotTestContext,
) -> None:
    """Test entities."""
    await snapshot_platform_entities(snapshot_context, Platform.SENSOR, "holidaymode")

    assert (
        snapshot_context.hass.states.get("climate.ndj_room_temperature").attributes[
            "preset_mode"
        ]
        == PRESET_AWAY
    )


async def _assert_water_heater_diagnostics(
    hass: HomeAssistant, config_entry: Any
) -> None:
    """Assert expected diagnostic data for the water-heater fixture."""
    config_diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    device = dr.async_get(hass).async_get_device_by_identifier(
        ("daikin_onecta", "1ece521b-5401-4a42-acce-6f76fba246aa"),
        config_entry.entry_id,
    )
    assert device is not None
    device_diagnostics = await async_get_device_diagnostics(hass, config_entry, device)
    for diagnostics in (config_diagnostics, device_diagnostics):
        assert diagnostics["rate_limits"] != ""
        assert diagnostics["options"] != ""
        assert diagnostics["oauth2_token_valid"] != ""


async def _exercise_initial_tank_temperature(
    hass: HomeAssistant, aioclient_mock: Any
) -> None:
    """Exercise a successful tank-temperature write and its no-op repeat."""
    for _ in range(2):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: "water_heater.altherma", ATTR_TEMPERATURE: 58},
            blocking=True,
        )
        await hass.async_block_till_done()
    info = await system_health_info(hass)
    assert info["remaining_minute"] == EXPECTED_REMAINING_MINUTE_RATE_LIMIT
    assert info["remaining_day"] == EXPECTED_REMAINING_DAY_RATE_LIMIT
    assert len(aioclient_mock.mock_calls) == EXPECTED_TANK_CALLS_AFTER_TEMPERATURE
    assert aioclient_mock.mock_calls[1][2] == {
        "value": 58,
        "path": "/operationModes/heating/setpoints/domesticHotWaterTemperature",
    }
    assert (
        hass.states.get("water_heater.altherma").attributes["temperature"]
        == EXPECTED_TANK_TEMPERATURE
    )


async def _assert_water_heater_update_noop(
    hass: HomeAssistant, aioclient_mock: Any
) -> None:
    """Assert that an update request is ignored directly after a write."""
    await async_setup_component(hass, "homeassistant", {})
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: "water_heater.altherma"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(aioclient_mock.mock_calls) == EXPECTED_TANK_CALLS_AFTER_TURN_ON


@pytest.mark.asyncio
async def test_water_heater(
    onecta_auth: AsyncMock,
    snapshot_context: SnapshotTestContext,
) -> None:
    """Test entities."""
    hass = snapshot_context.hass
    config_entry = snapshot_context.config_entry
    aioclient_mock = snapshot_context.aioclient_mock
    # Altherma with boost enabled
    await snapshot_platform_entities(
        snapshot_context, Platform.SENSOR, "altherma_boost"
    )

    await _assert_water_heater_diagnostics(hass, config_entry)

    assert (
        hass.states.get("water_heater.altherma").attributes["operation_mode"]
        == STATE_PERFORMANCE
    )

    with patch(
        "homeassistant.components.daikin_onecta.DaikinApi.async_get_access_token",
        return_value="XXXXXX",
    ):
        aioclient_mock.patch(
            DAIKIN_API_URL
            + "/v1/gateway-devices/1ece521b-5401-4a42-acce-6f76fba246aa/management-points/domesticHotWaterTank/characteristics/temperatureControl",
            status=204,
            headers={
                "X-RateLimit-Remaining-minute": "4",
                "X-RateLimit-Remaining-day": "10",
            },
        )

        await _exercise_initial_tank_temperature(hass, aioclient_mock)

        aioclient_mock.patch(
            DAIKIN_API_URL
            + "/v1/gateway-devices/1ece521b-5401-4a42-acce-6f76fba246aa/management-points/domesticHotWaterTank/characteristics/onOffMode",
            status=204,
        )

        # Set the tank off, this should just work
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_OPERATION_MODE,
            {ATTR_ENTITY_ID: "water_heater.altherma", ATTR_OPERATION_MODE: STATE_OFF},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_TANK_CALLS_AFTER_OFF
        assert aioclient_mock.mock_calls[2][2] == {"value": "off"}
        assert (
            hass.states.get("water_heater.altherma").attributes["operation_mode"]
            == STATE_OFF
        )

        # Set the tank temperature to 54, because the tank is off no call should be done to Daikin
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: "water_heater.altherma", ATTR_TEMPERATURE: 54},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_TANK_CALLS_AFTER_OFF
        assert (
            hass.states.get("water_heater.altherma").attributes["temperature"]
            == EXPECTED_TANK_TEMPERATURE
        )

        # aioclient_mock.patch(
        #     DAIKIN_API_URL
        #     + "/v1/gateway-devices/1ece521b-5401-4a42-acce-6f76fba246aa/management-points/domesticHotWaterTank/characteristics/onOffMode",
        #     status=204,
        # )
        aioclient_mock.patch(
            DAIKIN_API_URL
            + "/v1/gateway-devices/1ece521b-5401-4a42-acce-6f76fba246aa/management-points/domesticHotWaterTank/characteristics/powerfulMode",
            status=204,
        )

        # Set the tank to powerful mode, this should result in two calls, first turn the device
        # on and second to set it to performance
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_OPERATION_MODE,
            {
                ATTR_ENTITY_ID: "water_heater.altherma",
                ATTR_OPERATION_MODE: STATE_PERFORMANCE,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_TANK_CALLS_AFTER_PERFORMANCE
        assert aioclient_mock.mock_calls[3][2] == {"value": "on"}
        assert aioclient_mock.mock_calls[4][2] == {"value": "on"}
        assert (
            hass.states.get("water_heater.altherma").attributes["operation_mode"]
            == STATE_PERFORMANCE
        )

        # aioclient_mock.patch(
        #     DAIKIN_API_URL
        #     + "/v1/gateway-devices/1ece521b-5401-4a42-acce-6f76fba246aa/management-points/domesticHotWaterTank/characteristics/powerfulMode",
        #     status=204,
        # )

        # Set the tank to regular on mode, this should only disable powerful mode
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_OPERATION_MODE,
            {
                ATTR_ENTITY_ID: "water_heater.altherma",
                ATTR_OPERATION_MODE: STATE_HEAT_PUMP,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_TANK_CALLS_AFTER_HEAT_PUMP
        assert aioclient_mock.mock_calls[5][2] == {"value": "off"}
        assert (
            hass.states.get("water_heater.altherma").attributes["operation_mode"]
            == STATE_HEAT_PUMP
        )

        # aioclient_mock.patch(
        #     DAIKIN_API_URL
        #     + "/v1/gateway-devices/1ece521b-5401-4a42-acce-6f76fba246aa/management-points/domesticHotWaterTank/characteristics/onOffMode",
        #     status=204,
        # )

        # Turn the tank again off
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_OPERATION_MODE,
            {ATTR_ENTITY_ID: "water_heater.altherma", ATTR_OPERATION_MODE: STATE_OFF},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_TANK_CALLS_AFTER_SECOND_OFF
        assert aioclient_mock.mock_calls[6][2] == {"value": "off"}
        assert (
            hass.states.get("water_heater.altherma").attributes["operation_mode"]
            == STATE_OFF
        )

        # aioclient_mock.patch(
        #     DAIKIN_API_URL
        #     + "/v1/gateway-devices/1ece521b-5401-4a42-acce-6f76fba246aa/management-points/domesticHotWaterTank/characteristics/onOffMode",
        #     status=204,
        # )

        # Turn the tank again on
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_OPERATION_MODE,
            {
                ATTR_ENTITY_ID: "water_heater.altherma",
                ATTR_OPERATION_MODE: STATE_HEAT_PUMP,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_TANK_CALLS_AFTER_SECOND_ON
        assert aioclient_mock.mock_calls[7][2] == {"value": "on"}
        assert (
            hass.states.get("water_heater.altherma").attributes["operation_mode"]
            == STATE_HEAT_PUMP
        )

        # aioclient_mock.patch(
        #     DAIKIN_API_URL
        #     + "/v1/gateway-devices/1ece521b-5401-4a42-acce-6f76fba246aa/management-points/domesticHotWaterTank/characteristics/onOffMode",
        #     status=204,
        # )

        # Turn the tank again off using turn_off
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "water_heater.altherma"},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_TANK_CALLS_AFTER_TURN_OFF
        assert aioclient_mock.mock_calls[8][2] == {"value": "off"}
        assert (
            hass.states.get("water_heater.altherma").attributes["operation_mode"]
            == STATE_OFF
        )

        # Turn the tank again off using turn_off, will be a noop
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "water_heater.altherma"},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_TANK_CALLS_AFTER_TURN_OFF

        # aioclient_mock.patch(
        #     DAIKIN_API_URL
        #     + "/v1/gateway-devices/1ece521b-5401-4a42-acce-6f76fba246aa/management-points/domesticHotWaterTank/characteristics/onOffMode",
        #     status=204,
        # )

        # Turn the tank again on using turn_on
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "water_heater.altherma"},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_TANK_CALLS_AFTER_TURN_ON
        assert aioclient_mock.mock_calls[9][2] == {"value": "on"}
        assert (
            hass.states.get("water_heater.altherma").attributes["operation_mode"]
            == STATE_HEAT_PUMP
        )

        # Turn the tank again on using turn_on, will be a noop
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "water_heater.altherma"},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_TANK_CALLS_AFTER_TURN_ON

        await _assert_water_heater_update_noop(hass, aioclient_mock)

        aioclient_mock.clear_requests()
        aioclient_mock.patch(
            DAIKIN_API_URL
            + "/v1/gateway-devices/1ece521b-5401-4a42-acce-6f76fba246aa/management-points/domesticHotWaterTank/characteristics/onOffMode",
            status=429,
            headers={"X-RateLimit-Limit-minute": "0", "X-RateLimit-Limit-day": "0"},
        )

        # Turn the tank off, this should fail and not work due to the daily limit
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "water_heater.altherma"},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_FAILED_TANK_WRITE_CALLS
        assert aioclient_mock.mock_calls[0][2] == {"value": "off"}
        assert (
            hass.states.get("water_heater.altherma").attributes["operation_mode"]
            == STATE_HEAT_PUMP
        )

        aioclient_mock.clear_requests()
        aioclient_mock.patch(
            DAIKIN_API_URL
            + "/v1/gateway-devices/1ece521b-5401-4a42-acce-6f76fba246aa/management-points/domesticHotWaterTank/characteristics/onOffMode",
            status=204,
        )

        # Turn the tank off, this should work again
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "water_heater.altherma"},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == 1
        assert aioclient_mock.mock_calls[0][2] == {"value": "off"}
        assert (
            hass.states.get("water_heater.altherma").attributes["operation_mode"]
            == STATE_OFF
        )

        aioclient_mock.clear_requests()
        aioclient_mock.patch(
            DAIKIN_API_URL
            + "/v1/gateway-devices/1ece521b-5401-4a42-acce-6f76fba246aa/management-points/domesticHotWaterTank/characteristics/onOffMode",
            status=429,
            headers={"X-RateLimit-Limit-minute": "0", "X-RateLimit-Limit-day": "0"},
        )

        # Turn the tank on, this should fail and not work due to the daily limit
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "water_heater.altherma"},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == 1
        assert aioclient_mock.mock_calls[0][2] == {"value": "on"}
        assert (
            hass.states.get("water_heater.altherma").attributes["operation_mode"]
            == STATE_OFF
        )


@pytest.mark.asyncio
async def test_climate(
    onecta_auth: AsyncMock,
    snapshot_context: SnapshotTestContext,
) -> None:
    """Test entities."""
    hass = snapshot_context.hass
    aioclient_mock = snapshot_context.aioclient_mock
    await snapshot_platform_entities(snapshot_context, Platform.SENSOR, "altherma")

    _assert_initial_climate_state(hass)

    with patch(
        "homeassistant.components.daikin_onecta.DaikinApi.async_get_access_token",
        return_value="XXXXXX",
    ):
        aioclient_mock.patch(
            DAIKIN_API_URL
            + "/v1/gateway-devices/6f944461-08cb-4fee-979c-710ff66cea77/management-points/climateControl/characteristics/temperatureControl",
            status=204,
        )
        aioclient_mock.patch(
            DAIKIN_API_URL
            + "/v1/gateway-devices/6f944461-08cb-4fee-979c-710ff66cea77/management-points/climateControl/characteristics/onOffMode",
            status=204,
        )
        aioclient_mock.patch(
            DAIKIN_API_URL
            + "/v1/gateway-devices/6f944461-08cb-4fee-979c-710ff66cea77/management-points/climateControl/characteristics/operationMode",
            status=204,
        )
        aioclient_mock.patch(
            DAIKIN_API_URL
            + "/v1/gateway-devices/6f944461-08cb-4fee-979c-710ff66cea77/management-points/climateControl/characteristics/fanControl",
            status=204,
        )
        aioclient_mock.patch(
            DAIKIN_API_URL
            + "/v1/gateway-devices/6f944461-08cb-4fee-979c-710ff66cea77/management-points/climateControl/characteristics/powerfulMode",
            status=204,
        )
        aioclient_mock.patch(
            DAIKIN_API_URL
            + "/v1/gateway-devices/6f944461-08cb-4fee-979c-710ff66cea77/management-points/climateControl/characteristics/streamerMode",
            status=204,
        )
        aioclient_mock.post(
            DAIKIN_API_URL
            + "/v1/gateway-devices/6f944461-08cb-4fee-979c-710ff66cea77/management-points/climateControl/holiday-mode",
            status=204,
        )
        aioclient_mock.put(
            DAIKIN_API_URL
            + "/v1/gateway-devices/6f944461-08cb-4fee-979c-710ff66cea77/management-points/climateControl/schedule/any/current",
            status=204,
        )

        # Turn on the device, it was in cool mode
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "climate.werkkamer_room_temperature"},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_FIRST_ON
        assert aioclient_mock.mock_calls[1][2] == {"value": "on"}
        assert (
            hass.states.get("climate.werkkamer_room_temperature").state == HVACMode.COOL
        )

        # Turn on the device another time, this shouldn't result in a call to Daikin
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "climate.werkkamer_room_temperature"},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_FIRST_ON

        # Turn off the device, it was in cool mode
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "climate.werkkamer_room_temperature"},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_FIRST_OFF
        assert aioclient_mock.mock_calls[2][2] == {"value": "off"}
        assert (
            hass.states.get("climate.werkkamer_room_temperature").state == HVACMode.OFF
        )

        # Turn off the device another time, this shouldn't result in a call to Daikin
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "climate.werkkamer_room_temperature"},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_FIRST_OFF

        # Turn on the device in cooling through hvac mode
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_HVAC_MODE: HVACMode.COOL,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_COOL
        assert aioclient_mock.mock_calls[3][2] == {"value": "on"}
        assert (
            hass.states.get("climate.werkkamer_room_temperature").state == HVACMode.COOL
        )

        # Change the device to heating
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_HVAC_MODE: HVACMode.HEAT,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_HEAT
        assert aioclient_mock.mock_calls[4][2] == {"value": "heating"}
        assert (
            hass.states.get("climate.werkkamer_room_temperature").state == HVACMode.HEAT
        )

        # Turn off the device through the hvac mode
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_HVAC_MODE: HVACMode.OFF,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_HVAC_OFF
        assert aioclient_mock.mock_calls[5][2] == {"value": "off"}
        assert (
            hass.states.get("climate.werkkamer_room_temperature").state == HVACMode.OFF
        )

        # Turn on the device, it was in heat mode
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "climate.werkkamer_room_temperature"},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_HEAT_ON
        assert aioclient_mock.mock_calls[6][2] == {"value": "on"}
        assert (
            hass.states.get("climate.werkkamer_room_temperature").state == HVACMode.HEAT
        )

        # Set the fan mode to 2, will first set the fanControl to fixed, after that the value to 2
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: "climate.werkkamer_room_temperature", ATTR_FAN_MODE: 2},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_FIXED_FAN
        assert aioclient_mock.mock_calls[7][2] == {
            "value": "fixed",
            "path": "/operationModes/heating/fanSpeed/currentMode",
        }
        assert aioclient_mock.mock_calls[8][2] == {
            "value": 2,
            "path": "/operationModes/heating/fanSpeed/modes/fixed",
        }
        assert (
            hass.states.get("climate.werkkamer_room_temperature").attributes["fan_mode"]
            == "2"
        )

        # Set the fan mode again to 2, shouldn't result in any calls
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: "climate.werkkamer_room_temperature", ATTR_FAN_MODE: 2},
            blocking=True,
        )
        await hass.async_block_till_done()
        assert len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_FIXED_FAN

        # Set the fan mode to 3, should result in 1 call
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: "climate.werkkamer_room_temperature", ATTR_FAN_MODE: 3},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_FAN_SPEED
        assert aioclient_mock.mock_calls[9][2] == {
            "value": 3,
            "path": "/operationModes/heating/fanSpeed/modes/fixed",
        }
        assert (
            hass.states.get("climate.werkkamer_room_temperature").attributes["fan_mode"]
            == "3"
        )

        # Set the fan mode to auto, should result in 1 call
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_FAN_MODE: "auto",
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_AUTO_FAN
        assert aioclient_mock.mock_calls[10][2] == {
            "value": "auto",
            "path": "/operationModes/heating/fanSpeed/currentMode",
        }
        assert (
            hass.states.get("climate.werkkamer_room_temperature").attributes["fan_mode"]
            == "auto"
        )

        # Set the fan mode again to auto, should result in 0 call
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_FAN_MODE: "auto",
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_AUTO_FAN

        # Set the target temperature to 25
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_TEMPERATURE: 25,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert (
            len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_TEMPERATURE
        )
        assert aioclient_mock.mock_calls[11][2] == {
            "value": 25.0,
            "path": "/operationModes/heating/setpoints/roomTemperature",
        }
        assert (
            hass.states.get("climate.werkkamer_room_temperature").attributes[
                "temperature"
            ]
            == EXPECTED_CLIMATE_TARGET_TEMPERATURE
        )

        # Set the target temperature another time to 25, should not result in a call to Daikin
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_TEMPERATURE: 25,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert (
            len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_TEMPERATURE
        )

        # Set the hvac mode to cool and target temperature to 20 using one call
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_HVAC_MODE: HVACMode.COOL,
                ATTR_TEMPERATURE: 20,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert (
            len(aioclient_mock.mock_calls)
            == EXPECTED_CLIMATE_CALLS_AFTER_COOL_TEMPERATURE
        )
        assert aioclient_mock.mock_calls[12][2] == {"value": "cooling"}
        assert aioclient_mock.mock_calls[13][2] == {
            "value": 20.0,
            "path": "/operationModes/cooling/setpoints/roomTemperature",
        }
        assert (
            hass.states.get("climate.werkkamer_room_temperature").state == HVACMode.COOL
        )
        assert (
            hass.states.get("climate.werkkamer_room_temperature").attributes[
                "temperature"
            ]
            == EXPECTED_COOL_TARGET_TEMPERATURE
        )

        # Set the horizontal swing mode to swing
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_SWING_HORIZONTAL_MODE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_SWING_HORIZONTAL_MODE: "swing",
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        # Set the vertical swing mode to swing
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_SWING_MODE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_SWING_MODE: "swing",
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_SWING
        assert aioclient_mock.mock_calls[14][2] == {
            "value": "swing",
            "path": "/operationModes/cooling/fanDirection/horizontal/currentMode",
        }
        assert aioclient_mock.mock_calls[15][2] == {
            "value": "swing",
            "path": "/operationModes/cooling/fanDirection/vertical/currentMode",
        }
        assert (
            hass.states.get("climate.werkkamer_room_temperature").attributes[
                "swing_horizontal_mode"
            ]
            == "swing"
        )
        assert (
            hass.states.get("climate.werkkamer_room_temperature").attributes[
                "swing_mode"
            ]
            == "swing"
        )

        # Set the horizontal swing mode another time to swing, should not result in a call
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_SWING_HORIZONTAL_MODE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_SWING_HORIZONTAL_MODE: "swing",
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        # Set the vertical swing mode another time to swing, should not result in a call
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_SWING_MODE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_SWING_MODE: "swing",
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_SWING

        # Set the preset mode boost
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_PRESET_MODE: PRESET_BOOST,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_BOOST
        assert aioclient_mock.mock_calls[16][2] == {"value": "on"}
        assert (
            hass.states.get("climate.werkkamer_room_temperature").attributes[
                "preset_mode"
            ]
            == PRESET_BOOST
        )

        # Disable the preset mode boost again
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_PRESET_MODE: PRESET_NONE,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_BOOST_OFF
        assert aioclient_mock.mock_calls[17][2] == {"value": "off"}
        assert (
            hass.states.get("climate.werkkamer_room_temperature").attributes[
                "preset_mode"
            ]
            == PRESET_NONE
        )

        # Turn off the device through the hvac mode
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_HVAC_MODE: HVACMode.OFF,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert (
            len(aioclient_mock.mock_calls)
            == EXPECTED_CLIMATE_CALLS_AFTER_SECOND_HVAC_OFF
        )
        assert aioclient_mock.mock_calls[18][2] == {"value": "off"}
        assert (
            hass.states.get("climate.werkkamer_room_temperature").state == HVACMode.OFF
        )

        # Set the preset mode boost, this should result in two calls, power on the device
        # and set the preset mode. The device was in cool mode, so check that here
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_PRESET_MODE: PRESET_BOOST,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert (
            len(aioclient_mock.mock_calls)
            == EXPECTED_CLIMATE_CALLS_AFTER_BOOST_POWER_ON
        )
        assert aioclient_mock.mock_calls[19][2] == {"value": "on"}
        assert aioclient_mock.mock_calls[20][2] == {"value": "on"}
        assert (
            hass.states.get("climate.werkkamer_room_temperature").attributes[
                "preset_mode"
            ]
            == PRESET_BOOST
        )
        assert (
            hass.states.get("climate.werkkamer_room_temperature").state == HVACMode.COOL
        )

        # Test streamer mode switch
        assert (
            hass.states.get("switch.werkkamer_climatecontrol_streamer_mode").state
            == STATE_OFF
        )

        # Set the streamer mode on
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.werkkamer_climatecontrol_streamer_mode"},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert (
            len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_STREAMER_ON
        )
        assert aioclient_mock.mock_calls[21][2] == {"value": "on"}
        assert (
            hass.states.get("switch.werkkamer_climatecontrol_streamer_mode").state
            == STATE_ON
        )

        # Set the streamer mode on a second time shouldn't result in a call to daikin
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.werkkamer_climatecontrol_streamer_mode"},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert (
            len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_STREAMER_ON
        )

        # Set the streamer mode off
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.werkkamer_climatecontrol_streamer_mode"},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert (
            len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_STREAMER_OFF
        )
        assert aioclient_mock.mock_calls[22][2] == {"value": "off"}
        assert (
            hass.states.get("switch.werkkamer_climatecontrol_streamer_mode").state
            == STATE_OFF
        )

        # Set the streamer mode off a second time shouldn't result in a call to daikin
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.werkkamer_climatecontrol_streamer_mode"},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert (
            len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_STREAMER_OFF
        )

        # Set the device in away mode (away mode)
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_PRESET_MODE: PRESET_AWAY,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_AWAY
        assert aioclient_mock.mock_calls[24][2] == {
            "enabled": True,
            "startDate": dt_util.now().date().isoformat(),
            "endDate": (dt_util.now().date() + timedelta(days=60)).isoformat(),
        }
        assert (
            hass.states.get("climate.werkkamer_room_temperature").attributes[
                "preset_mode"
            ]
            == PRESET_AWAY
        )

        # Set the device in preset mode none again
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_PRESET_MODE: PRESET_NONE,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_AWAY_OFF
        assert aioclient_mock.mock_calls[25][2] == {"enabled": False}
        assert (
            hass.states.get("climate.werkkamer_room_temperature").attributes[
                "preset_mode"
            ]
            == PRESET_NONE
        )

        # Set the device with schedule 0 enabled
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.werkkamer_climatecontrol_schedule",
                ATTR_OPTION: "0",
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert (
            len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_SCHEDULE_ON
        )
        assert aioclient_mock.mock_calls[26][2] == {"scheduleId": "0", "enabled": True}
        assert hass.states.get("select.werkkamer_climatecontrol_schedule").state == "0"

        # Set the device with no schedule
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.werkkamer_climatecontrol_schedule",
                ATTR_OPTION: SCHEDULE_OFF,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert (
            len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_SCHEDULE_OFF
        )
        assert aioclient_mock.mock_calls[27][2] == {"scheduleId": "0", "enabled": False}
        assert (
            hass.states.get("select.werkkamer_climatecontrol_schedule").state
            == SCHEDULE_OFF
        )

        aioclient_mock.put(
            DAIKIN_API_URL
            + "/v1/gateway-devices/1ece521b-5401-4a42-acce-6f76fba246aa/management-points/climateControlMainZone/schedule/cooling/current",
            status=204,
        )

        # Set the device with schedule 'User defined' enabled
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.altherma_climatecontrol_schedule",
                ATTR_OPTION: "User defined",
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert (
            len(aioclient_mock.mock_calls)
            == EXPECTED_CLIMATE_CALLS_AFTER_CUSTOM_SCHEDULE_ON
        )
        assert aioclient_mock.mock_calls[28][2] == {
            "scheduleId": "scheduleCoolingRT1",
            "enabled": True,
        }
        assert (
            hass.states.get("select.altherma_climatecontrol_schedule").state
            == "User defined"
        )

        # Set the device with no schedule
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.altherma_climatecontrol_schedule",
                ATTR_OPTION: SCHEDULE_OFF,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert (
            len(aioclient_mock.mock_calls)
            == EXPECTED_CLIMATE_CALLS_AFTER_CUSTOM_SCHEDULE_OFF
        )
        assert aioclient_mock.mock_calls[29][2] == {
            "scheduleId": "scheduleCoolingRT1",
            "enabled": False,
        }
        assert (
            hass.states.get("select.altherma_climatecontrol_schedule").state
            == SCHEDULE_OFF
        )

        # Turn off the device through the hvac mode
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_HVAC_MODE: HVACMode.OFF,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_FINAL_OFF
        assert aioclient_mock.mock_calls[30][2] == {"value": "off"}
        assert (
            hass.states.get("climate.werkkamer_room_temperature").state == HVACMode.OFF
        )

        # Turn off the device through the hvac mode, because it is already off it shouldn't result
        # in a call to daikin
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_HVAC_MODE: HVACMode.OFF,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_FINAL_OFF
        assert (
            hass.states.get("climate.werkkamer_room_temperature").state == HVACMode.OFF
        )

        # Enable dry mode
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_HVAC_MODE: HVACMode.DRY,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_DRY
        assert (
            hass.states.get("climate.werkkamer_room_temperature").state == HVACMode.DRY
        )

        # In order to call update_entity we need to setup the HA core
        await async_setup_component(hass, "homeassistant", {})

        # We patch the scan_ignore method to zero so that the coordinator will pull again
        with patch(
            "homeassistant.components.daikin_onecta.OnectaDataUpdateCoordinator.scan_ignore",
            return_value=0,
        ):
            aioclient_mock.get(
                DAIKIN_API_URL + "/v1/gateway-devices",
                status=200,
                json=load_fixture_json("altherma"),
            )
            # Call update_entity service to trigger an update
            await hass.services.async_call(
                HA_DOMAIN,
                SERVICE_UPDATE_ENTITY,
                {ATTR_ENTITY_ID: "climate.werkkamer_room_temperature"},
                blocking=True,
            )
            await hass.async_block_till_done()

            assert len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_UPDATE
            assert aioclient_mock.mock_calls[33][1] == URL(
                DAIKIN_API_URL + "/v1/gateway-devices"
            )

        # Set the swing mode to windnice, should result in a call with windNice
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_SWING_MODE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_SWING_MODE: "windnice",
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert (
            len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_CALLS_AFTER_SWING_ALIAS
        )
        assert aioclient_mock.mock_calls[34][2] == {
            "value": "windNice",
            "path": "/operationModes/cooling/fanDirection/vertical/currentMode",
        }
        assert (
            hass.states.get("climate.werkkamer_room_temperature").attributes[
                "swing_mode"
            ]
            == "windnice"
        )

        aioclient_mock.clear_requests()
        aioclient_mock.put(
            DAIKIN_API_URL
            + "/v1/gateway-devices/1ece521b-5401-4a42-acce-6f76fba246aa/management-points/climateControlMainZone/schedule/cooling/current",
            status=429,
            headers={
                "X-RateLimit-Remaining-minute": "0",
                "X-RateLimit-Remaining-day": "0",
            },
        )
        # Set the device with schedule 'User defined' enabled, this should fail due to the rate limit
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.altherma_climatecontrol_schedule",
                ATTR_OPTION: "User defined",
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        info = await system_health_info(hass)

        assert info["remaining_minute"] == 0
        assert info["remaining_day"] == 0

        assert len(aioclient_mock.mock_calls) == 1
        assert aioclient_mock.mock_calls[0][2] == {
            "scheduleId": "scheduleCoolingRT1",
            "enabled": True,
        }
        assert (
            hass.states.get("select.altherma_climatecontrol_schedule").state
            == SCHEDULE_OFF
        )

        aioclient_mock.clear_requests()
        aioclient_mock.patch(
            DAIKIN_API_URL
            + "/v1/gateway-devices/6f944461-08cb-4fee-979c-710ff66cea77/management-points/climateControl/characteristics/onOffMode",
            status=500,
        )
        # Try to enable cooling, this fails, so the device should stay off
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_HVAC_MODE: HVACMode.COOL,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == 1
        assert (
            hass.states.get("climate.werkkamer_room_temperature").state == HVACMode.OFF
        )

        aioclient_mock.clear_requests()
        aioclient_mock.patch(
            DAIKIN_API_URL
            + "/v1/gateway-devices/6f944461-08cb-4fee-979c-710ff66cea77/management-points/climateControl/characteristics/onOffMode",
            status=204,
        )
        aioclient_mock.patch(
            DAIKIN_API_URL
            + "/v1/gateway-devices/6f944461-08cb-4fee-979c-710ff66cea77/management-points/climateControl/characteristics/operationMode",
            status=500,
        )
        # Try to enable heating, changing on/off works but setting operation mode now fails
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: "climate.werkkamer_room_temperature",
                ATTR_HVAC_MODE: HVACMode.HEAT,
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_CLIMATE_WRITE_CALLS
        assert (
            hass.states.get("climate.werkkamer_room_temperature").state == HVACMode.OFF
        )


@pytest.mark.asyncio
async def test_minimal_data(
    onecta_auth: AsyncMock,
    snapshot_context: SnapshotTestContext,
) -> None:
    """Test entities."""
    await snapshot_platform_entities(snapshot_context, Platform.SENSOR, "minimal_data")

    assert (
        snapshot_context.hass.states.get("water_heater.altherma").attributes[
            "current_temperature"
        ]
        == EXPECTED_MINIMAL_DATA_WATER_TEMPERATURE
    )
    assert (
        snapshot_context.hass.states.get(
            "sensor.altherma_domestichotwatertank_heating_yearly_electrical_consumption"
        ).state
        == "1232"
    )


@pytest.mark.asyncio
async def test_gas(
    onecta_auth: AsyncMock,
    snapshot_context: SnapshotTestContext,
) -> None:
    """Test entities."""
    hass = snapshot_context.hass
    aioclient_mock = snapshot_context.aioclient_mock
    await snapshot_platform_entities(snapshot_context, Platform.SENSOR, "gas")

    assert (
        hass.states.get("climate.my_living_room_room_temperature").attributes[
            "temperature"
        ]
        == EXPECTED_GAS_ROOM_TEMPERATURE
    )

    with patch(
        "homeassistant.components.daikin_onecta.DaikinApi.async_get_access_token",
        return_value="XXXXXX",
    ):
        aioclient_mock.clear_requests()
        aioclient_mock.get(
            DAIKIN_API_URL + "/v1/gateway-devices",
            status=429,
            json=load_fixture_json("dry"),
            headers={
                "X-RateLimit-Remaining-minute": "0",
                "X-RateLimit-Remaining-day": "0",
            },
        )

        # Call button service
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.my_living_room_refresh"},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == 1
        assert aioclient_mock.mock_calls[0][1] == URL(
            DAIKIN_API_URL + "/v1/gateway-devices"
        )

        info = await system_health_info(hass)

        assert info["remaining_minute"] == 0
        assert info["remaining_day"] == 0

    with patch(
        "homeassistant.components.daikin_onecta.DaikinApi.async_get_access_token",
        return_value="XXXXXX",
    ):
        aioclient_mock.clear_requests()
        aioclient_mock.get(
            DAIKIN_API_URL + "/v1/gateway-devices", status=200, text="TET {"
        )

        # Call button service
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.my_living_room_refresh"},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == 1
        assert aioclient_mock.mock_calls[0][1] == URL(
            DAIKIN_API_URL + "/v1/gateway-devices"
        )

        aioclient_mock.clear_requests()
        aioclient_mock.get(
            DAIKIN_API_URL + "/v1/gateway-devices", status=300, json="TEST"
        )

        # Call button service
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.my_living_room_refresh"},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == 1
        assert aioclient_mock.mock_calls[0][1] == URL(
            DAIKIN_API_URL + "/v1/gateway-devices"
        )


@pytest.mark.asyncio
async def test_button(
    onecta_auth: AsyncMock,
    snapshot_context: SnapshotTestContext,
) -> None:
    """Test entities."""
    hass = snapshot_context.hass
    aioclient_mock = snapshot_context.aioclient_mock
    await snapshot_platform_entities(snapshot_context, Platform.SENSOR, "dry")

    with patch(
        "homeassistant.components.daikin_onecta.DaikinApi.async_get_access_token",
        return_value="XXXXXX",
    ):
        aioclient_mock.get(
            DAIKIN_API_URL + "/v1/gateway-devices",
            status=200,
            json=load_fixture_json("dry"),
        )

        # Call button service
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.lounge_refresh"},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert len(aioclient_mock.mock_calls) == EXPECTED_BUTTON_WRITE_CALLS


@pytest.mark.asyncio
async def test_altherma_schedule(
    onecta_auth: AsyncMock,
    snapshot_context: SnapshotTestContext,
) -> None:
    """Test entities."""
    hass = snapshot_context.hass
    await snapshot_platform_entities(
        snapshot_context, Platform.SENSOR, "altherma_schedule"
    )

    assert (
        hass.states.get("select.altherma_domestichotwatertank_schedule").state
        == "User defined"
    )


@pytest.mark.asyncio
async def test_altherma_firmwareupdate(
    onecta_auth: AsyncMock,
    snapshot_context: SnapshotTestContext,
) -> None:
    """Test entities."""
    hass = snapshot_context.hass
    await snapshot_platform_entities(
        snapshot_context, Platform.SENSOR, "altherma_firmwareupdate"
    )
    await hass.async_block_till_done()

    assert (
        hass.states.get(
            "update.climate_control_getr422_gateway_firmware_update"
        ).attributes["installed_version"]
        == "4.0.1"
    )
    assert (
        hass.states.get(
            "update.climate_control_getr422_gateway_firmware_update"
        ).attributes["latest_version"]
        == "4.1.901"
    )
    assert (
        hass.states.get(
            "update.climate_control_getr422_gateway_firmware_update"
        ).attributes["release_summary"]
        == "Altherma WLAN update 4.1.901"
    )
    assert (
        hass.states.get(
            "update.climate_control_getr422_gateway_firmware_update"
        ).attributes["in_progress"]
        is True
    )
    assert (
        hass.states.get(
            "update.climate_control_getr422_userinterface_firmware_update"
        ).attributes["installed_version"]
        == "3.12.1"
    )
    assert (
        hass.states.get(
            "update.climate_control_getr422_userinterface_firmware_update"
        ).attributes["latest_version"]
        == "3.12.1"
    )


@pytest.mark.asyncio
async def test_dx4_firmwareupdate(
    onecta_auth: AsyncMock,
    snapshot_context: SnapshotTestContext,
) -> None:
    """Test entities."""
    hass = snapshot_context.hass
    aioclient_mock = snapshot_context.aioclient_mock
    await snapshot_platform_entities(
        snapshot_context, Platform.SENSOR, "dx4_firmwareavailable"
    )

    assert (
        hass.states.get("update.johnny_maaike_gateway_firmware_update").attributes[
            "installed_version"
        ]
        == "2_0_0"
    )
    assert (
        hass.states.get("update.johnny_maaike_gateway_firmware_update").attributes[
            "latest_version"
        ]
        == "2_3_0"
    )
    assert (
        hass.states.get("update.johnny_maaike_gateway_firmware_update").attributes[
            "release_summary"
        ]
        == "DX4 WLAN security update 2_3_0"
    )
    assert (
        hass.states.get("update.johnny_maaike_gateway_firmware_update").attributes[
            "in_progress"
        ]
        is False
    )

    with patch(
        "homeassistant.components.daikin_onecta.DaikinApi.async_get_access_token",
        return_value="XXXXXX",
    ):
        aioclient_mock.put(
            DAIKIN_API_URL
            + "/v1/gateway-devices/32db6075-b739-4026-b661-127009254b42/management-points/gateway/firmware/5db22235-b750-401f-afd6-6d05841ffcc3",
            status=204,
        )

        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {
                ATTR_ENTITY_ID: "update.johnny_maaike_gateway_firmware_update",
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        assert len(aioclient_mock.mock_calls) == EXPECTED_FIRMWARE_WRITE_CALLS


@pytest.mark.asyncio
async def test_skyair(
    onecta_auth: AsyncMock,
    snapshot_context: SnapshotTestContext,
) -> None:
    """Test entities."""
    await snapshot_platform_entities(snapshot_context, Platform.SENSOR, "skyair")


def test_device_fill_info_missing_management_point() -> None:
    """Leave device info unchanged except manufacturer when the point type is absent."""
    gateway = GatewayDevice(
        id="device",
        device_model="model",
        management_points=[],
        cloud_connection=Characteristic(value=True),
    )
    device = DaikinOnectaDevice(gateway, MagicMock())
    info = {}

    device.fill_device_info(info, "missing")

    assert info == {"manufacturer": "Daikin"}


def test_device_fill_info_uses_embedded_management_point_id() -> None:
    """Use the selected zone's metadata when management-point types repeat."""
    point = MagicMock(
        eeprom_version=None,
        firmware_version=None,
        serial_number=None,
        software_version=None,
    )
    point.model_info.value = "Second zone model"
    device = object.__new__(DaikinOnectaDevice)
    device.device = MagicMock()
    device.device.management_point.return_value = point
    info = {}

    device.fill_device_info(info, "climateControlZone2")

    device.device.management_point.assert_called_once_with("climateControlZone2")
    assert info == {"manufacturer": "Daikin", "model": "Second zone model"}


def test_migrate_legacy_subdevice_identifier(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Preserve the existing subdevice record when moving to an embedded ID."""
    config_entry.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    legacy_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "deviceclimateControl")},
    )
    management_point = MagicMock(
        management_point_type="climateControl", embedded_id="zone1"
    )
    device = MagicMock(id="device")
    device.device.management_points = [management_point]

    migrate_legacy_subdevice_identifiers(hass, config_entry, {"device": device})

    migrated_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "devicezone1"), config_entry.entry_id
    )
    assert migrated_entry is not None
    assert migrated_entry.id == legacy_entry.id
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "deviceclimateControl"), config_entry.entry_id
        )
        is None
    )


def test_migrate_legacy_sensor_unique_ids(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Preserve existing entities while adding management-point details to IDs."""
    config_entry.add_to_hass(hass)
    entity_registry = er.async_get(hass)
    value_entry = entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="device_climateControl_None_roomTemperature",
        config_entry=config_entry,
    )
    energy_entry = entity_registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="device_climateControl_electrical_heating_d",
        config_entry=config_entry,
    )
    management_point = MagicMock(
        management_point_type="climateControl", embedded_id="zone1"
    )
    device = MagicMock(id="device")
    device.device.management_points = [management_point]

    migrate_legacy_sensor_unique_ids(hass, config_entry, {"device": device})

    assert (
        entity_registry.async_get(value_entry.entity_id).unique_id
        == "device_zone1_None_roomTemperature"
    )
    assert (
        entity_registry.async_get(energy_entry.entity_id).unique_id
        == "device_zone1_electrical_heating_d_consumption"
    )


def test_migrate_legacy_entity_unique_ids(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Preserve entities while replacing management-point types with IDs."""
    config_entry.add_to_hass(hass)
    entity_registry = er.async_get(hass)
    legacy_entries = [
        entity_registry.async_get_or_create(
            domain, DOMAIN, unique_id, config_entry=config_entry
        )
        for domain, unique_id in (
            ("binary_sensor", "device_climateControl_None_isInErrorState"),
            ("select", "device_climateControl_schedule"),
            ("switch", "device_climateControl_testMode"),
            ("update", "device_climateControl_firmware_update"),
            ("climate", "device_roomTemperature"),
            ("water_heater", "device"),
        )
    ]
    climate_control = MagicMock(
        management_point_type="climateControl", embedded_id="zone1"
    )
    water_tank = MagicMock(
        management_point_type="domesticHotWaterTank", embedded_id="tank"
    )
    device = MagicMock(id="device")
    device.device.management_points = [climate_control, water_tank]

    migrate_legacy_entity_unique_ids(hass, config_entry, {"device": device})

    assert [
        entity_registry.async_get(entry.entity_id).unique_id for entry in legacy_entries
    ] == [
        "device_zone1_None_isInErrorState",
        "device_zone1_schedule",
        "device_zone1_testMode",
        "device_zone1_firmware_update",
        "device_zone1_roomTemperature",
        "device_tank",
    ]

    migrate_legacy_update_unique_ids(hass, config_entry)

    assert (
        entity_registry.async_get(legacy_entries[3].entity_id).unique_id
        == "device_zone1_firmware"
    )


def test_schedule_select_missing_selection() -> None:
    """Handle a schedule entity whose management point is no longer available."""
    device = MagicMock(id="device", name="Device", ha_device_id="ha-device")
    device.management_point.return_value = None
    entity = DaikinScheduleSelect(
        device, MagicMock(), "missing", "climateControl", "schedule"
    )

    assert entity.selection() is None
    assert entity.get_options() == []
    assert entity.get_current_option() == SCHEDULE_OFF


@pytest.mark.asyncio
async def test_schedule_select_missing_selection_on_write() -> None:
    """Ignore schedule writes when no selection is available."""
    device = MagicMock(id="device", name="Device", ha_device_id="ha-device")
    device.management_point.return_value = None
    entity = DaikinScheduleSelect(
        device, MagicMock(), "missing", "climateControl", "schedule"
    )
    entity.selection = MagicMock(return_value=None)

    assert await entity.async_select_option("Weekday") is False
    device.put.assert_not_called()


def test_system_health_register() -> None:
    """Register the system health callback."""
    register = MagicMock()

    async_register(MagicMock(), register)

    register.async_register_info.assert_called_once_with(system_health_info)


@pytest.mark.asyncio
async def test_system_health_without_config_entry(hass: HomeAssistant) -> None:
    """Return no system-health data when the integration is not configured."""
    assert await system_health_info(hass) == {}


@pytest.mark.asyncio
async def test_firmware_install_without_id() -> None:
    """Do not issue a firmware update request without a firmware ID."""
    device = MagicMock(id="device", name="Device", ha_device_id="ha-device")
    management_point = MagicMock(
        firmware_version=None,
        software_version=None,
        is_firmware_update_supported=None,
        firmware_update=None,
        firmware_update_status=None,
    )
    entity = DaikinFirmwareUpdateEntity(
        MagicMock(), device, management_point, "gateway"
    )

    await entity.async_install(None, False)

    device.put.assert_not_called()


@pytest.mark.asyncio
async def test_firmware_install_failure(caplog: pytest.LogCaptureFixture) -> None:
    """Log a failed firmware update request."""
    device = MagicMock(id="device", ha_device_id="ha-device")
    device.name = "Device"
    device.put = AsyncMock(return_value=False)
    management_point = MagicMock(
        firmware_version=MagicMock(value="1.0"),
        software_version=None,
        is_firmware_update_supported=MagicMock(value=True),
        firmware_update=MagicMock(value={"id": "firmware-id"}),
        firmware_update_status=None,
    )
    management_point.embedded_id = "gateway-id"
    entity = DaikinFirmwareUpdateEntity(
        MagicMock(), device, management_point, "gateway"
    )
    entity.async_write_ha_state = MagicMock()

    await entity.async_install(None, False)

    device.put.assert_awaited_once_with("device", "gateway-id", "firmware/firmware-id")
    assert "Failed to trigger firmware update for Device" in caplog.text


@pytest.mark.asyncio
async def test_switch_write_failures() -> None:
    """Keep switch state unchanged when cloud writes fail."""
    device = MagicMock(id="device", name="Device", ha_device_id="ha-device")
    device.management_point.return_value = None
    device.patch = AsyncMock(return_value=False)
    entity = DaikinSwitch(device, MagicMock(), "point", "climateControl", "testMode")

    await entity.async_turn_on()
    assert entity.is_on is False

    on_characteristic = MagicMock(value="on")
    on_management_point = MagicMock()
    on_management_point.characteristic.return_value = on_characteristic
    device.management_point.return_value = on_management_point
    on_entity = DaikinSwitch(device, MagicMock(), "point", "climateControl", "testMode")
    await on_entity.async_turn_off()
    assert on_entity.is_on is True


@pytest.mark.asyncio
async def test_successful_writes_update_cached_models() -> None:
    """Keep the cached model in sync while coordinator polling is deferred."""
    climate = object.__new__(DaikinClimate)
    climate_device = MagicMock(id="device", name="Device")
    climate_device.patch = AsyncMock(return_value=True)
    object.__setattr__(climate, "_device", climate_device)
    object.__setattr__(climate, "_embedded_id", "zone")
    object.__setattr__(climate, "_setpoint", "roomTemperature")
    object.__setattr__(climate, "_attr_target_temperature", 20)
    climate.operation_mode = MagicMock(return_value=MagicMock(value="heating"))
    climate_setpoint = MagicMock(value=20)
    climate.setpoint = MagicMock(return_value=climate_setpoint)
    climate.async_write_ha_state = MagicMock()

    await climate.async_set_temperature(temperature=21)

    assert climate_setpoint.value == 21

    switch = object.__new__(DaikinSwitch)
    switch_device = MagicMock(id="device", name="Device")
    switch_device.patch = AsyncMock(return_value=True)
    object.__setattr__(switch, "_device", switch_device)
    object.__setattr__(switch, "_embedded_id", "zone")
    object.__setattr__(switch, "_value", "testMode")
    object.__setattr__(switch, "_switch_state", "off")
    characteristic = MagicMock(value="off")
    switch_device.management_point.return_value.characteristic.return_value = (
        characteristic
    )
    switch.async_write_ha_state = MagicMock()

    await switch.async_turn_on()
    assert characteristic.value == "on"

    schedule = object.__new__(DaikinScheduleSelect)
    schedule_device = MagicMock(id="device", name="Device")
    schedule_device.put = AsyncMock(return_value=True)
    object.__setattr__(schedule, "_device", schedule_device)
    object.__setattr__(schedule, "_embedded_id", "zone")
    schedule_data = Schedule(
        current_mode=Characteristic(value="weekly"),
        modes={
            "weekly": {
                "currentSchedule": {"value": "old", "values": ["old", "new"]},
                "enabled": {"value": True, "settable": True},
                "schedules": {
                    "old": {"name": {"value": "Old schedule"}},
                    "new": {"name": {"value": "New schedule"}},
                },
            }
        },
    )
    schedule_point = MagicMock()
    schedule_point.schedule = Characteristic(value=schedule_data)
    schedule_device.management_point.return_value = schedule_point
    schedule.async_write_ha_state = MagicMock()

    assert await schedule.async_select_option("New schedule")
    assert schedule_data.modes["weekly"]["currentSchedule"]["value"] == "new"
    assert schedule_data.modes["weekly"]["enabled"]["value"] is True


@pytest.mark.asyncio
async def test_water_heater_non_settable_temperature() -> None:
    """Ignore target temperature changes when the setpoint is read-only."""
    entity = object.__new__(DaikinWaterTank)
    device = MagicMock(name="Tank")
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_attr_current_operation", STATE_HEAT_PUMP)
    setpoint = MagicMock()
    setpoint.settable = False
    entity.__dict__["domestic_hotwater_temperature"] = setpoint

    with patch.object(
        DaikinWaterTank,
        "domestic_hotwater_temperature",
        new_callable=lambda: property(lambda self: setpoint),
    ):
        await entity.async_set_tank_temperature(50)

    device.patch.assert_not_called()
