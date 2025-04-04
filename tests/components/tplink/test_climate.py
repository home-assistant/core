"""Tests for tplink climate platform."""

from datetime import timedelta

from kasa import Device, Feature, Module
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
    _mocked_device,
    _mocked_feature,
    setup_platform_for_device,
    snapshot_platform,
)
from .const import DEVICE_ID

from tests.common import MockConfigEntry, async_fire_time_changed

ENTITY_ID = "climate.thermostat"


@pytest.fixture
async def mocked_hub(hass: HomeAssistant) -> Device:
    """Return mocked tplink hub."""

    features = [
        _mocked_feature(
            "temperature",
            type_=Feature.Type.Number,
            category=Feature.Category.Primary,
            unit="celsius",
        ),
        _mocked_feature(
            "target_temperature",
            type_=Feature.Type.Number,
            category=Feature.Category.Primary,
            unit="celsius",
        ),
    ]

    thermostat = _mocked_device(
        alias="thermostat",
        features=features,
        modules=[Module.Thermostat],
        device_type=Device.Type.Thermostat,
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

    therm_module = mocked_thermostat.modules.get(Module.Thermostat)
    assert therm_module

    await setup_platform_for_device(
        hass, mock_config_entry, Platform.CLIMATE, mocked_hub
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 10},
        blocking=True,
    )

    therm_module.set_target_temperature.assert_called_with(10)


async def test_set_hvac_mode(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mocked_hub: Device
) -> None:
    """Test that set_hvac_mode service works."""
    await setup_platform_for_device(
        hass, mock_config_entry, Platform.CLIMATE, mocked_hub
    )

    mocked_thermostat = mocked_hub.children[0]
    therm_module = mocked_thermostat.modules.get(Module.Thermostat)
    assert therm_module

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )

    therm_module.set_state.assert_called_with(False)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: [ENTITY_ID], ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )
    therm_module.set_state.assert_called_with(True)

    msg = "Tried to set unsupported mode: dry"
    with pytest.raises(ServiceValidationError, match=msg):
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
    therm_module = mocked_thermostat.modules.get(Module.Thermostat)
    assert therm_module

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: [ENTITY_ID]},
        blocking=True,
    )

    therm_module.set_state.assert_called_with(False)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [ENTITY_ID]},
        blocking=True,
    )

    therm_module.set_state.assert_called_with(True)


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
    therm_module = mocked_thermostat.modules.get(Module.Thermostat)
    assert therm_module

    therm_module.mode = ThermostatState.Unknown

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF
    assert "Unknown thermostat state, defaulting to OFF" in caplog.text


async def test_missing_feature_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mocked_hub: Device,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a module missing the min/max and unit feature logs an error."""
    mocked_thermostat = mocked_hub.children[0]
    mocked_thermostat.features.pop("target_temperature")
    mocked_thermostat.features.pop("temperature")

    await setup_platform_for_device(
        hass, mock_config_entry, Platform.CLIMATE, mocked_hub
    )
    assert "Unable to get min/max target temperature" in caplog.text
    assert "Unable to get correct temperature unit" in caplog.text
