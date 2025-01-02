"""Tests for tplink climate platform."""

from datetime import timedelta

from kasa import Device, Feature
from kasa.smart.modules.temperaturecontrol import ThermostatState
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from . import (
    DEVICE_ID,
    _mocked_device,
    _mocked_feature,
    setup_platform_for_device,
    snapshot_platform,
)

from tests.common import MockConfigEntry, async_fire_time_changed

ENTITY_ID = "climate.thermostat"


@pytest.fixture
async def mocked_hub(hass: HomeAssistant) -> Device:
    """Return mocked tplink binary sensor feature."""

    features = [
        _mocked_feature(
            "temperature", value=20.2, category=Feature.Category.Primary, unit="celsius"
        ),
        _mocked_feature(
            "target_temperature",
            value=22.2,
            type_=Feature.Type.Number,
            category=Feature.Category.Primary,
            unit="celsius",
        ),
        _mocked_feature(
            "state",
            value=True,
            type_=Feature.Type.Switch,
            category=Feature.Category.Primary,
        ),
        _mocked_feature(
            "thermostat_mode",
            value=ThermostatState.Heating,
            type_=Feature.Type.Choice,
            category=Feature.Category.Primary,
        ),
    ]

    thermostat = _mocked_device(
        alias="thermostat", features=features, device_type=Device.Type.Thermostat
    )

    return _mocked_device(
        alias="hub", children=[thermostat], device_type=Device.Type.Hub
    )


async def test_climate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mocked_hub: Device,
) -> None:
    """Test initialization."""
    await setup_platform_for_device(
        hass, mock_config_entry, Platform.CLIMATE, mocked_hub
    )

    entity = entity_registry.async_get(ENTITY_ID)
    assert entity
    assert entity.unique_id == f"{DEVICE_ID}_climate"

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_HVAC_ACTION] is HVACAction.HEATING
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 20.2
    assert state.attributes[ATTR_TEMPERATURE] == 22.2


async def test_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    mocked_hub: Device,
) -> None:
    """Snapshot test."""
    await setup_platform_for_device(
        hass, mock_config_entry, Platform.CLIMATE, mocked_hub
    )

    await snapshot_platform(
        hass, entity_registry, device_registry, snapshot, mock_config_entry.entry_id
    )


async def test_set_temperature(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mocked_hub: Device
) -> None:
    """Test that set_temperature service calls the setter."""
    mocked_thermostat = mocked_hub.children[0]
    mocked_thermostat.features["target_temperature"].minimum_value = 0

    await setup_platform_for_device(
        hass, mock_config_entry, Platform.CLIMATE, mocked_hub
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 10},
        blocking=True,
    )
    target_temp_feature = mocked_thermostat.features["target_temperature"]
    target_temp_feature.set_value.assert_called_with(10)


async def test_set_hvac_mode(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mocked_hub: Device
) -> None:
    """Test that set_hvac_mode service works."""
    await setup_platform_for_device(
        hass, mock_config_entry, Platform.CLIMATE, mocked_hub
    )

    mocked_thermostat = mocked_hub.children[0]
    mocked_state = mocked_thermostat.features["state"]
    assert mocked_state is not None

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )

    mocked_state.set_value.assert_called_with(False)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: [ENTITY_ID], ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    mocked_state.set_value.assert_called_with(True)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: [ENTITY_ID], ATTR_HVAC_MODE: HVACMode.DRY},
            blocking=True,
        )


async def test_turn_on_and_off(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mocked_hub: Device
) -> None:
    """Test that turn_on and turn_off services work as expected."""
    await setup_platform_for_device(
        hass, mock_config_entry, Platform.CLIMATE, mocked_hub
    )

    mocked_thermostat = mocked_hub.children[0]
    mocked_state = mocked_thermostat.features["state"]

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: [ENTITY_ID]},
        blocking=True,
    )

    mocked_state.set_value.assert_called_with(False)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [ENTITY_ID]},
        blocking=True,
    )

    mocked_state.set_value.assert_called_with(True)


async def test_unknown_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mocked_hub: Device,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that unknown device modes log a warning and default to off."""
    await setup_platform_for_device(
        hass, mock_config_entry, Platform.CLIMATE, mocked_hub
    )

    mocked_thermostat = mocked_hub.children[0]
    mocked_state = mocked_thermostat.features["thermostat_mode"]
    mocked_state.value = ThermostatState.Unknown

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF
    assert "Unknown thermostat state, defaulting to OFF" in caplog.text
