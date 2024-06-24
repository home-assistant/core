"""Tests for tplink climate platform."""

from datetime import timedelta

from kasa import Device, Feature
from kasa.smart.modules.temperaturecontrol import ThermostatState
import pytest

from homeassistant.components import tplink
from homeassistant.components.climate import (
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
from homeassistant.components.tplink.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import (
    DEVICE_ID,
    MAC_ADDRESS,
    _mocked_device,
    _mocked_feature,
    _patch_connect,
    _patch_discovery,
)

from tests.common import MockConfigEntry, async_fire_time_changed

ENTITY_ID = "climate.thermostat"


@pytest.fixture
async def mocked_hub(hass: HomeAssistant) -> Device:
    """Return mocked tplink binary sensor feature."""
    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)

    features = [
        _mocked_feature(
            20, "temperature", category=Feature.Category.Primary, unit="celsius"
        ),
        _mocked_feature(
            22,
            "target_temperature",
            type_=Feature.Type.Number,
            category=Feature.Category.Primary,
            unit="celsius",
        ),
        _mocked_feature(
            True, "state", type_=Feature.Type.Switch, category=Feature.Category.Primary
        ),
        _mocked_feature(
            ThermostatState.Heating,
            "thermostat_mode",
            type_=Feature.Type.Choice,
            category=Feature.Category.Primary,
        ),
    ]

    thermostat = _mocked_device(
        alias="thermostat", features=features, device_type=Device.Type.Thermostat
    )

    device = _mocked_device(
        alias="hub", children=[thermostat], device_type=Device.Type.Hub
    )
    with _patch_discovery(device=device), _patch_connect(device=device):
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    return device


async def test_climate(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mocked_hub: Device
) -> None:
    """Test initialization."""
    entity = entity_registry.async_get(ENTITY_ID)
    assert entity
    assert entity.unique_id == f"{DEVICE_ID}_climate"


async def test_set_temperature(hass: HomeAssistant, mocked_hub: Device) -> None:
    """Test that set_temperature service calls the setter."""

    mocked_thermostat = mocked_hub.children[0]

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 10},
        blocking=True,
    )
    target_temp_feature = mocked_thermostat.features["target_temperature"]
    target_temp_feature.set_value.assert_called_with(10)


async def test_set_hvac_mode(hass: HomeAssistant, mocked_hub: Device) -> None:
    """Test that set_hvac_mode service works."""
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


async def test_turn_on_and_off(hass: HomeAssistant, mocked_hub: Device) -> None:
    """Test that turn_on and turn_off services work as expected."""
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
    hass: HomeAssistant, mocked_hub: Device, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that set_temperature service calls the setter."""

    mocked_thermostat = mocked_hub.children[0]
    mocked_state = mocked_thermostat.features["thermostat_mode"]
    mocked_state.value = ThermostatState.Unknown

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF
    assert "Unknown thermostat state, defaulting to OFF" in caplog.text
