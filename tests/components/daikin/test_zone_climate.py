"""Tests for Daikin zone climate entities."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.climate import (
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.daikin.const import DOMAIN, KEY_MAC
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    CONF_HOST,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from .conftest import ZoneDevice, configure_zone_device

from tests.common import MockConfigEntry

HOST = "127.0.0.1"


async def _async_setup_daikin(
    hass: HomeAssistant, zone_device: ZoneDevice
) -> MockConfigEntry:
    """Set up a Daikin config entry with a mocked library device."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=zone_device.mac,
        data={CONF_HOST: HOST, KEY_MAC: zone_device.mac},
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


def _zone_entity_id(
    entity_registry: er.EntityRegistry, zone_device: ZoneDevice, zone_id: int
) -> str | None:
    """Return the entity id for a zone climate unique id."""
    return entity_registry.async_get_entity_id(
        CLIMATE_DOMAIN,
        DOMAIN,
        f"{zone_device.mac}-zone{zone_id}-temperature",
    )


def _zone_switch_entity_id(
    entity_registry: er.EntityRegistry, zone_device: ZoneDevice, zone_id: int
) -> str | None:
    """Return the entity id for a zone switch unique id."""
    return entity_registry.async_get_entity_id(
        SWITCH_DOMAIN,
        DOMAIN,
        f"{zone_device.mac}-zone{zone_id}",
    )


async def _async_set_zone_temperature(
    hass: HomeAssistant, entity_id: str, temperature: float
) -> None:
    """Call `climate.set_temperature` for a zone climate."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TEMPERATURE: temperature,
        },
        blocking=True,
    )


async def test_setup_entry_adds_zone_climates(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
) -> None:
    """Configured zones create zone climate entities."""
    configure_zone_device(
        zone_device, zones=[["-", "0", 0], ["Living", "1", 22], ["Office", "1", 21]]
    )

    await _async_setup_daikin(hass, zone_device)

    assert _zone_entity_id(entity_registry, zone_device, 0) is None
    assert _zone_entity_id(entity_registry, zone_device, 1) is not None
    assert _zone_entity_id(entity_registry, zone_device, 2) is not None


async def test_setup_entry_skips_zone_climates_without_support(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
) -> None:
    """Missing zone temperature lists skip zone climate entities."""
    configure_zone_device(zone_device, zones=[["Living", "1", 22]])
    zone_device.values["lztemp_h"] = ""
    zone_device.values["lztemp_c"] = ""

    await _async_setup_daikin(hass, zone_device)

    assert _zone_entity_id(entity_registry, zone_device, 0) is None


async def test_setup_entry_handles_missing_zone_temperature_key(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
) -> None:
    """Missing zone temperature keys do not break climate setup."""
    configure_zone_device(zone_device, zones=[["Living", "1", 22]])
    zone_device.values.pop("lztemp_h")

    await _async_setup_daikin(hass, zone_device)

    assert _zone_entity_id(entity_registry, zone_device, 0) is None
    main_entity_id = entity_registry.async_get_entity_id(
        CLIMATE_DOMAIN,
        DOMAIN,
        zone_device.mac,
    )
    assert main_entity_id is not None
    assert hass.states.get(main_entity_id) is not None


@pytest.mark.parametrize(
    ("mode", "expected_zone_key"),
    [("hot", "lztemp_h"), ("cool", "lztemp_c")],
)
async def test_zone_climate_sets_temperature_for_active_mode(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
    mode: str,
    expected_zone_key: str,
) -> None:
    """Setting temperature updates the active mode zone value."""
    configure_zone_device(
        zone_device,
        zones=[["Living", "0", 22], ["Office", "1", 21]],
        mode=mode,
    )
    await _async_setup_daikin(hass, zone_device)
    entity_id = _zone_entity_id(entity_registry, zone_device, 0)
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_TEMPERATURE] == 22.0

    await _async_set_zone_temperature(hass, entity_id, 23)

    zone_device.set_zone.assert_awaited_once_with(0, expected_zone_key, "23")


async def test_zone_climate_rejects_out_of_range_temperature(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
) -> None:
    """Service validation rejects values outside the allowed range."""
    configure_zone_device(
        zone_device,
        zones=[["Living", "1", 22]],
        target_temperature=22,
    )
    await _async_setup_daikin(hass, zone_device)
    entity_id = _zone_entity_id(entity_registry, zone_device, 0)
    assert entity_id is not None

    with pytest.raises(ServiceValidationError) as err:
        await _async_set_zone_temperature(hass, entity_id, 30)

    assert err.value.translation_key == "temp_out_of_range"


async def test_zone_climate_unavailable_without_target_temperature(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
) -> None:
    """Zones are unavailable if system target temperature is missing."""
    configure_zone_device(
        zone_device,
        zones=[["Living", "1", 22]],
        target_temperature=None,
    )
    await _async_setup_daikin(hass, zone_device)
    entity_id = _zone_entity_id(entity_registry, zone_device, 0)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_zone_climate_zone_inactive_after_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
) -> None:
    """Inactive zones raise a translated error during service calls."""
    configure_zone_device(zone_device, zones=[["Living", "1", 22]])
    await _async_setup_daikin(hass, zone_device)
    entity_id = _zone_entity_id(entity_registry, zone_device, 0)
    assert entity_id is not None
    zone_device.zones[0][0] = "-"

    with pytest.raises(HomeAssistantError) as err:
        await _async_set_zone_temperature(hass, entity_id, 21)

    assert err.value.translation_key == "zone_inactive"


async def test_zone_climate_zone_missing_after_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
) -> None:
    """Missing zones raise a translated error during service calls."""
    configure_zone_device(
        zone_device,
        zones=[["Living", "1", 22], ["Office", "1", 22]],
    )
    await _async_setup_daikin(hass, zone_device)
    entity_id = _zone_entity_id(entity_registry, zone_device, 1)
    assert entity_id is not None
    zone_device.zones = [["Living", "1", 22]]

    with pytest.raises(HomeAssistantError) as err:
        await _async_set_zone_temperature(hass, entity_id, 21)

    assert err.value.translation_key == "zone_missing"


async def test_zone_climate_parameters_unavailable(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
) -> None:
    """Missing zone parameter lists make the zone entity unavailable."""
    configure_zone_device(zone_device, zones=[["Living", "1", 22]])
    await _async_setup_daikin(hass, zone_device)
    entity_id = _zone_entity_id(entity_registry, zone_device, 0)
    assert entity_id is not None
    zone_device.values["lztemp_h"] = ""
    zone_device.values["lztemp_c"] = ""

    await async_update_entity(hass, entity_id)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_zone_climate_hvac_modes_read_only(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
) -> None:
    """Changing HVAC mode through a zone climate is blocked."""
    configure_zone_device(zone_device, zones=[["Living", "1", 22]])
    await _async_setup_daikin(hass, zone_device)
    entity_id = _zone_entity_id(entity_registry, zone_device, 0)
    assert entity_id is not None

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_HVAC_MODE: HVACMode.HEAT,
            },
            blocking=True,
        )

    assert err.value.translation_key == "zone_hvac_read_only"


async def test_zone_climate_set_temperature_requires_heat_or_cool(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
) -> None:
    """Setting temperature in unsupported modes raises a translated error."""
    configure_zone_device(
        zone_device,
        zones=[["Living", "1", 22]],
        mode="auto",
    )
    await _async_setup_daikin(hass, zone_device)
    entity_id = _zone_entity_id(entity_registry, zone_device, 0)
    assert entity_id is not None

    with pytest.raises(HomeAssistantError) as err:
        await _async_set_zone_temperature(hass, entity_id, 21)

    assert err.value.translation_key == "zone_hvac_mode_unsupported"


@pytest.mark.parametrize(
    ("zone_state", "expected_state", "expected_action"),
    [
        pytest.param("1", HVACMode.COOL, HVACAction.COOLING, id="zone-on"),
        pytest.param("0", HVACMode.OFF, HVACAction.OFF, id="zone-off"),
    ],
)
async def test_zone_climate_properties(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
    zone_state: str,
    expected_state: HVACMode,
    expected_action: HVACAction,
) -> None:
    """Zone climate exposes expected state attributes."""
    configure_zone_device(
        zone_device,
        zones=[["Living", zone_state, 22]],
        target_temperature=24,
        mode="cool",
        heating_values="20",
        cooling_values="18",
    )
    await _async_setup_daikin(hass, zone_device)
    entity_id = _zone_entity_id(entity_registry, zone_device, 0)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state
    assert state.attributes[ATTR_HVAC_ACTION] == expected_action
    assert state.attributes[ATTR_TEMPERATURE] == 18.0
    assert state.attributes[ATTR_MIN_TEMP] == 22.0
    assert state.attributes[ATTR_MAX_TEMP] == 26.0
    assert state.attributes[ATTR_HVAC_MODES] == [HVACMode.COOL]
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    assert state.attributes["zone_id"] == 0


@pytest.mark.parametrize(
    (
        "service",
        "initial_zone_state",
        "expected_zone_state",
        "expected_climate_state",
        "expected_switch_state",
        "main_mode",
    ),
    [
        pytest.param(
            SERVICE_TURN_ON,
            "0",
            "1",
            HVACMode.COOL,
            STATE_ON,
            "cool",
            id="climate-turn-on",
        ),
        pytest.param(
            SERVICE_TURN_OFF,
            "1",
            "0",
            HVACMode.OFF,
            STATE_OFF,
            "cool",
            id="climate-turn-off",
        ),
        pytest.param(
            SERVICE_TOGGLE,
            "1",
            "0",
            HVACMode.OFF,
            STATE_OFF,
            "cool",
            id="climate-toggle-off",
        ),
        pytest.param(
            SERVICE_TOGGLE,
            "1",
            "0",
            HVACMode.OFF,
            STATE_OFF,
            "off",
            id="climate-toggle-zone-on-main-off",
        ),
    ],
)
async def test_zone_climate_power_controls(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
    service: str,
    initial_zone_state: str,
    expected_zone_state: str,
    expected_climate_state: HVACMode,
    expected_switch_state: str,
    main_mode: str,
) -> None:
    """Zone climate and switch power controls stay synchronized."""
    configure_zone_device(
        zone_device,
        zones=[["Living", initial_zone_state, 22]],
        mode=main_mode,
    )

    async def set_zone(zone_id: int, key: str, value: str) -> None:
        assert key == "zone_onoff"
        zone_device.zones[zone_id][1] = value

    zone_device.set_zone.side_effect = set_zone
    await _async_setup_daikin(hass, zone_device)
    climate_entity_id = _zone_entity_id(entity_registry, zone_device, 0)
    switch_entity_id = _zone_switch_entity_id(entity_registry, zone_device, 0)
    assert climate_entity_id is not None
    assert switch_entity_id is not None

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: climate_entity_id},
        blocking=True,
    )

    zone_device.set_zone.assert_awaited_once_with(0, "zone_onoff", expected_zone_state)
    zone_device.set.assert_not_awaited()
    climate_state = hass.states.get(climate_entity_id)
    switch_state = hass.states.get(switch_entity_id)
    assert climate_state is not None
    assert switch_state is not None
    assert climate_state.state == expected_climate_state
    assert switch_state.state == expected_switch_state


async def test_zone_switch_updates_zone_climate(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
) -> None:
    """The existing zone switch updates the zone climate state."""
    configure_zone_device(
        zone_device,
        zones=[["Living", "1", 22]],
        mode="cool",
    )

    async def set_zone(zone_id: int, key: str, value: str) -> None:
        assert key == "zone_onoff"
        zone_device.zones[zone_id][1] = value

    zone_device.set_zone.side_effect = set_zone
    await _async_setup_daikin(hass, zone_device)
    climate_entity_id = _zone_entity_id(entity_registry, zone_device, 0)
    switch_entity_id = _zone_switch_entity_id(entity_registry, zone_device, 0)
    assert climate_entity_id is not None
    assert switch_entity_id is not None

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: switch_entity_id},
        blocking=True,
    )

    zone_device.set_zone.assert_awaited_once_with(0, "zone_onoff", "0")
    zone_device.set.assert_not_awaited()
    climate_state = hass.states.get(climate_entity_id)
    switch_state = hass.states.get(switch_entity_id)
    assert climate_state is not None
    assert switch_state is not None
    assert climate_state.state == HVACMode.OFF
    assert switch_state.state == STATE_OFF


@pytest.mark.parametrize(
    ("mode", "expected_state"),
    [
        pytest.param("auto", HVACMode.HEAT_COOL, id="auto"),
        pytest.param("off", HVACMode.OFF, id="off"),
    ],
)
async def test_zone_climate_target_temperature_inactive_mode(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
    mode: str,
    expected_state: HVACMode,
) -> None:
    """In non-heating/cooling modes, zone target temperature is None."""
    configure_zone_device(
        zone_device,
        zones=[["Living", "1", 22]],
        mode=mode,
        heating_values="bad",
        cooling_values="19",
    )
    await _async_setup_daikin(hass, zone_device)
    entity_id = _zone_entity_id(entity_registry, zone_device, 0)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state
    assert state.attributes[ATTR_TEMPERATURE] is None


async def test_zone_climate_set_zone_failed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    zone_device: ZoneDevice,
) -> None:
    """Service call surfaces backend zone update errors."""
    configure_zone_device(zone_device, zones=[["Living", "1", 22]])
    await _async_setup_daikin(hass, zone_device)
    entity_id = _zone_entity_id(entity_registry, zone_device, 0)
    assert entity_id is not None
    zone_device.set_zone = AsyncMock(side_effect=NotImplementedError)

    with pytest.raises(HomeAssistantError) as err:
        await _async_set_zone_temperature(hass, entity_id, 21)

    assert err.value.translation_key == "zone_set_failed"
