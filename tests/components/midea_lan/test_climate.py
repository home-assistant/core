"""Tests for midea_lan climate.py."""

from unittest.mock import patch

from midealocal.const import DeviceType
from midealocal.devices.ac import DeviceAttributes as ACAttributes
from midealocal.devices.c3.const import DeviceAttributes as C3Attributes
from midealocal.devices.cc import DeviceAttributes as CCAttributes
from midealocal.devices.cf import DeviceAttributes as CFAttributes
from midealocal.devices.fb import DeviceAttributes as FBAttributes
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HVAC_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_STEP,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_LOW,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SWING_BOTH,
    SWING_ON,
    SWING_VERTICAL,
    HVACMode,
)
from homeassistant.components.midea_lan.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import DummyDevice
from .const import BASE_DATA

from tests.common import MockConfigEntry, snapshot_platform


async def _async_setup_entry(
    hass: HomeAssistant,
    device: DummyDevice,
) -> MockConfigEntry:
    """Set up a Midea LAN config entry with a fake device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**BASE_DATA, CONF_TYPE: device.device_type},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.midea_lan.device_selector",
        return_value=device,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)

    return entry


def _entity_entries(
    hass: HomeAssistant, entry: MockConfigEntry
) -> dict[str, er.RegistryEntry]:
    """Return entity registry entries keyed by unique id."""
    entity_registry = er.async_get(hass)
    return {
        entity_entry.unique_id: entity_entry
        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        )
    }


async def _assert_service_calls(
    hass: HomeAssistant,
    entity_id: str,
    service: str,
    service_data: dict,
    expected_calls: list[tuple],
    device: DummyDevice,
) -> None:
    """Call a climate service and assert the fake device recorded the right call."""
    device.calls.clear()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id, **service_data},
        blocking=True,
    )
    assert device.calls == expected_calls


async def test_midea_ac_climate_setup_and_services(hass: HomeAssistant) -> None:
    """Test AC climate entities are created and service calls reach the device."""
    device = DummyDevice(
        DeviceType.AC,
        attributes={
            ACAttributes.power: True,
            ACAttributes.mode: 1,
            ACAttributes.target_temperature: 22.0,
            ACAttributes.indoor_temperature: 21.0,
            ACAttributes.comfort_mode: False,
            ACAttributes.eco_mode: False,
            ACAttributes.boost_mode: False,
            ACAttributes.sleep_mode: False,
            ACAttributes.frost_protect: False,
            ACAttributes.fan_speed: 103,
            ACAttributes.swing_vertical: True,
            ACAttributes.swing_horizontal: True,
            ACAttributes.indoor_humidity: 50,
        },
    )
    entry = await _async_setup_entry(hass, device)
    entity_entry = _entity_entries(hass, entry)["123_climate"]

    state = hass.states.get(entity_entry.entity_id)
    assert state is not None
    assert state.state == HVACMode.AUTO
    assert state.attributes[ATTR_CURRENT_HUMIDITY] == 50.0
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 21.0
    assert state.attributes[ATTR_FAN_MODE] == "auto"
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.DRY,
        HVACMode.HEAT,
        HVACMode.FAN_ONLY,
    ]
    assert state.attributes[ATTR_MAX_TEMP] == 30
    assert state.attributes[ATTR_MIN_TEMP] == 16
    assert state.attributes[ATTR_PRESET_MODE] is None
    assert state.attributes[ATTR_SWING_MODE] == SWING_BOTH
    assert state.attributes[ATTR_TARGET_TEMP_STEP] == 1.0
    assert state.attributes[ATTR_TEMPERATURE] == 22.0

    await _assert_service_calls(
        hass,
        entity_entry.entity_id,
        SERVICE_TURN_OFF,
        {},
        [("set_attribute", ACAttributes.power, False)],
        device,
    )
    await _assert_service_calls(
        hass,
        entity_entry.entity_id,
        SERVICE_TURN_ON,
        {},
        [("set_attribute", ACAttributes.power, True)],
        device,
    )
    await _assert_service_calls(
        hass,
        entity_entry.entity_id,
        SERVICE_SET_TEMPERATURE,
        {ATTR_TEMPERATURE: 23.1, "hvac_mode": HVACMode.COOL},
        [
            (
                "set_target_temperature",
                {"target_temperature": 23.1, "mode": 2, "zone": None},
            )
        ],
        device,
    )
    await _assert_service_calls(
        hass,
        entity_entry.entity_id,
        SERVICE_SET_HVAC_MODE,
        {"hvac_mode": HVACMode.HEAT},
        [("set_attribute", ACAttributes.mode, 4)],
        device,
    )
    await _assert_service_calls(
        hass,
        entity_entry.entity_id,
        SERVICE_SET_FAN_MODE,
        {ATTR_FAN_MODE: FAN_LOW},
        [("set_attribute", ACAttributes.fan_speed, 40)],
        device,
    )
    await _assert_service_calls(
        hass,
        entity_entry.entity_id,
        SERVICE_SET_SWING_MODE,
        {ATTR_SWING_MODE: SWING_VERTICAL},
        [("set_swing", {"swing_vertical": True, "swing_horizontal": False})],
        device,
    )
    await _assert_service_calls(
        hass,
        entity_entry.entity_id,
        SERVICE_SET_PRESET_MODE,
        {ATTR_PRESET_MODE: PRESET_COMFORT},
        [("set_attribute", ACAttributes.comfort_mode, True)],
        device,
    )
    device.attributes.update(
        {
            ACAttributes.comfort_mode: True,
            ACAttributes.eco_mode: False,
            ACAttributes.boost_mode: False,
            ACAttributes.sleep_mode: False,
            ACAttributes.frost_protect: False,
        }
    )
    await _assert_service_calls(
        hass,
        entity_entry.entity_id,
        SERVICE_SET_PRESET_MODE,
        {ATTR_PRESET_MODE: PRESET_ECO},
        [
            ("set_attribute", ACAttributes.comfort_mode, False),
            ("set_attribute", ACAttributes.eco_mode, True),
        ],
        device,
    )
    device.attributes.update(
        {
            ACAttributes.comfort_mode: True,
            ACAttributes.eco_mode: False,
            ACAttributes.boost_mode: False,
            ACAttributes.sleep_mode: False,
            ACAttributes.frost_protect: False,
        }
    )
    await _assert_service_calls(
        hass,
        entity_entry.entity_id,
        SERVICE_SET_PRESET_MODE,
        {ATTR_PRESET_MODE: PRESET_NONE},
        [("set_attribute", ACAttributes.comfort_mode, False)],
        device,
    )


async def test_midea_cc_climate_setup_and_services(hass: HomeAssistant) -> None:
    """Test CC climate entities are created and exposed through hass.states."""
    device = DummyDevice(
        DeviceType.CC,
        attributes={
            CCAttributes.power: True,
            CCAttributes.mode: 5,
            CCAttributes.fan_speed: "high",
            CCAttributes.temperature_precision: 0.5,
            CCAttributes.swing: True,
        },
    )
    entry = await _async_setup_entry(hass, device)
    entity_entry = _entity_entries(hass, entry)["123_climate"]

    state = hass.states.get(entity_entry.entity_id)
    assert state is not None
    assert state.state == HVACMode.AUTO
    assert state.attributes[ATTR_FAN_MODE] == "high"
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVACMode.OFF,
        HVACMode.FAN_ONLY,
        HVACMode.DRY,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.AUTO,
    ]
    assert state.attributes[ATTR_PRESET_MODE] is None
    assert state.attributes[ATTR_SWING_MODE] == SWING_ON
    assert state.attributes[ATTR_TARGET_TEMP_STEP] == 0.5

    await _assert_service_calls(
        hass,
        entity_entry.entity_id,
        SERVICE_SET_FAN_MODE,
        {ATTR_FAN_MODE: FAN_LOW},
        [("set_attribute", CCAttributes.fan_speed, "low")],
        device,
    )
    await _assert_service_calls(
        hass,
        entity_entry.entity_id,
        SERVICE_SET_SWING_MODE,
        {ATTR_SWING_MODE: SWING_ON},
        [("set_attribute", CCAttributes.swing, True)],
        device,
    )


async def test_midea_cf_climate_setup_and_services(hass: HomeAssistant) -> None:
    """Test CF climate entities are created and control calls are routed."""
    device = DummyDevice(
        DeviceType.CF,
        attributes={
            "power": True,
            "mode": 2,
            CFAttributes.min_temperature: 16,
            CFAttributes.max_temperature: 30,
            CFAttributes.current_temperature: 22,
        },
    )
    entry = await _async_setup_entry(hass, device)
    entity_entry = _entity_entries(hass, entry)["123_climate"]

    state = hass.states.get(entity_entry.entity_id)
    assert state is not None
    assert state.state == HVACMode.COOL
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 22.0
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.HEAT,
    ]
    assert state.attributes[ATTR_MAX_TEMP] == 30
    assert state.attributes[ATTR_MIN_TEMP] == 16
    assert state.attributes[ATTR_TARGET_TEMP_STEP] == 1.0

    await _assert_service_calls(
        hass,
        entity_entry.entity_id,
        SERVICE_SET_TEMPERATURE,
        {ATTR_TEMPERATURE: 24.2, "hvac_mode": HVACMode.OFF},
        [("set_attribute", CCAttributes.power, False)],
        device,
    )
    await _assert_service_calls(
        hass,
        entity_entry.entity_id,
        SERVICE_SET_HVAC_MODE,
        {"hvac_mode": HVACMode.HEAT},
        [("set_attribute", CCAttributes.mode, 3)],
        device,
    )


async def test_midea_c3_climate_setup_and_services(hass: HomeAssistant) -> None:
    """Test C3 climate entities are created and zone-specific services work."""
    device = DummyDevice(
        DeviceType.C3,
        attributes={
            C3Attributes.zone_temp_type: [True, False],
            C3Attributes.temperature_min: [16, 17],
            C3Attributes.temperature_max: [30, 29],
            C3Attributes.mode: 1,
            C3Attributes.zone1_power: True,
            C3Attributes.target_temperature: [22, 23],
            C3Attributes.temp_tw_in: [21.5, 22.5],
        },
    )
    entry = await _async_setup_entry(hass, device)
    entity_entries = _entity_entries(hass, entry)

    zone1 = entity_entries["123_climate_zone1"]
    zone2 = entity_entries["123_climate_zone2"]
    assert zone2.disabled_by == er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(zone2.entity_id) is None

    state = hass.states.get(zone1.entity_id)
    assert state is not None
    assert state.state == HVACMode.AUTO
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 21.5
    assert state.attributes[ATTR_HVAC_MODES] == [
        HVACMode.OFF,
        HVACMode.AUTO,
        HVACMode.COOL,
        HVACMode.HEAT,
    ]
    assert state.attributes[ATTR_MAX_TEMP] == 30
    assert state.attributes[ATTR_MIN_TEMP] == 16
    assert state.attributes[ATTR_TARGET_TEMP_STEP] == 1.0
    assert state.attributes[ATTR_TEMPERATURE] == 22.0

    await _assert_service_calls(
        hass,
        zone1.entity_id,
        SERVICE_SET_TEMPERATURE,
        {ATTR_TEMPERATURE: 21.4, "hvac_mode": HVACMode.COOL},
        [
            (
                "set_target_temperature",
                {"target_temperature": 21.4, "mode": 2, "zone": 0},
            )
        ],
        device,
    )
    await _assert_service_calls(
        hass,
        zone1.entity_id,
        SERVICE_SET_HVAC_MODE,
        {"hvac_mode": HVACMode.OFF},
        [("set_attribute", C3Attributes.zone1_power, False)],
        device,
    )
    await _assert_service_calls(
        hass,
        zone1.entity_id,
        SERVICE_SET_HVAC_MODE,
        {"hvac_mode": HVACMode.HEAT},
        [("set_mode", 0, 3)],
        device,
    )


async def test_midea_fb_climate_setup_and_services(hass: HomeAssistant) -> None:
    """Test FB climate entities are created and preset calls are routed."""
    device = DummyDevice(
        DeviceType.FB,
        attributes={
            FBAttributes.mode: "comfort",
            FBAttributes.power: True,
            FBAttributes.current_temperature: 20,
        },
    )
    entry = await _async_setup_entry(hass, device)
    entity_entry = _entity_entries(hass, entry)["123_climate"]

    state = hass.states.get(entity_entry.entity_id)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 20.0
    assert state.attributes[ATTR_HVAC_MODES] == [HVACMode.OFF, HVACMode.HEAT]
    assert state.attributes[ATTR_MAX_TEMP] == 35
    assert state.attributes[ATTR_MIN_TEMP] == 5
    assert state.attributes[ATTR_PRESET_MODE] == "comfort"
    assert state.attributes[ATTR_TARGET_TEMP_STEP] == 1.0

    await _assert_service_calls(
        hass,
        entity_entry.entity_id,
        SERVICE_SET_TEMPERATURE,
        {ATTR_TEMPERATURE: 24.2, "hvac_mode": HVACMode.OFF},
        [("set_attribute", FBAttributes.power, False)],
        device,
    )
    await _assert_service_calls(
        hass,
        entity_entry.entity_id,
        SERVICE_SET_HVAC_MODE,
        {"hvac_mode": HVACMode.HEAT},
        [("set_attribute", FBAttributes.power, True)],
        device,
    )
    await _assert_service_calls(
        hass,
        entity_entry.entity_id,
        SERVICE_SET_PRESET_MODE,
        {ATTR_PRESET_MODE: PRESET_ECO},
        [("set_attribute", FBAttributes.mode, PRESET_ECO)],
        device,
    )


@pytest.mark.parametrize(
    ("fan_speed", "expected_fan_mode"),
    [
        pytest.param(103, "auto", id="auto"),
        pytest.param(0, "silent", id="silent_fallback"),
    ],
)
async def test_ac_fan_mode_thresholds(
    hass: HomeAssistant,
    fan_speed: int,
    expected_fan_mode: str,
) -> None:
    """Test AC fan mode mapping including silent fallback."""
    device = DummyDevice(
        DeviceType.AC,
        attributes={
            ACAttributes.power: True,
            ACAttributes.mode: 1,
            ACAttributes.target_temperature: 22.0,
            ACAttributes.indoor_temperature: 21.0,
            ACAttributes.fan_speed: fan_speed,
            ACAttributes.swing_vertical: True,
            ACAttributes.swing_horizontal: True,
            ACAttributes.indoor_humidity: 50,
        },
    )
    entry = await _async_setup_entry(hass, device)
    entity_entry = _entity_entries(hass, entry)["123_climate"]

    assert (state := hass.states.get(entity_entry.entity_id))
    assert state.attributes[ATTR_FAN_MODE] == expected_fan_mode


@pytest.mark.parametrize(
    ("humidity", "expected_humidity"),
    [
        pytest.param(50, 50.0, id="normal"),
        pytest.param(0, None, id="invalid_zero"),
        pytest.param(0xFF, None, id="invalid_ff"),
    ],
)
async def test_ac_humidity_filtering(
    hass: HomeAssistant,
    humidity: int,
    expected_humidity: float | None,
) -> None:
    """Test AC humidity filtering for invalid sensor values."""
    device = DummyDevice(
        DeviceType.AC,
        attributes={
            ACAttributes.power: True,
            ACAttributes.mode: 1,
            ACAttributes.target_temperature: 22.0,
            ACAttributes.indoor_temperature: 21.0,
            ACAttributes.fan_speed: 103,
            ACAttributes.swing_vertical: True,
            ACAttributes.swing_horizontal: True,
            ACAttributes.indoor_humidity: humidity,
        },
    )
    entry = await _async_setup_entry(hass, device)
    entity_entry = _entity_entries(hass, entry)["123_climate"]

    assert (state := hass.states.get(entity_entry.entity_id))
    assert state.attributes.get(ATTR_CURRENT_HUMIDITY) == expected_humidity


async def test_base_set_temperature_without_target_noop(hass: HomeAssistant) -> None:
    """Test set_temperature without ATTR_TEMPERATURE is ignored."""
    device = DummyDevice(
        DeviceType.AC,
        attributes={
            ACAttributes.power: True,
            ACAttributes.mode: 1,
            ACAttributes.target_temperature: 22.0,
            ACAttributes.indoor_temperature: 21.0,
            ACAttributes.fan_speed: 103,
            ACAttributes.swing_vertical: True,
            ACAttributes.swing_horizontal: True,
        },
    )
    entry = await _async_setup_entry(hass, device)
    entity_entry = _entity_entries(hass, entry)["123_climate"]
    entity = hass.data[CLIMATE_DOMAIN].get_entity(entity_entry.entity_id)

    device.calls.clear()
    assert entity is not None
    entity.set_temperature()
    assert device.calls == []


async def test_ac_set_hvac_mode_off_calls_power_off(hass: HomeAssistant) -> None:
    """Test AC HVAC off delegates to turn_off."""
    device = DummyDevice(
        DeviceType.AC,
        attributes={
            ACAttributes.power: True,
            ACAttributes.mode: 1,
            ACAttributes.target_temperature: 22.0,
            ACAttributes.indoor_temperature: 21.0,
            ACAttributes.fan_speed: 103,
            ACAttributes.swing_vertical: True,
            ACAttributes.swing_horizontal: True,
        },
    )
    entry = await _async_setup_entry(hass, device)
    entity_entry = _entity_entries(hass, entry)["123_climate"]

    await _assert_service_calls(
        hass,
        entity_entry.entity_id,
        SERVICE_SET_HVAC_MODE,
        {"hvac_mode": HVACMode.OFF},
        [("set_attribute", ACAttributes.power, False)],
        device,
    )


async def test_ac_invalid_mode_maps_to_off_state(hass: HomeAssistant) -> None:
    """Test AC invalid protocol mode yields off state."""
    device = DummyDevice(
        DeviceType.AC,
        attributes={
            ACAttributes.power: True,
            ACAttributes.mode: 999,
            ACAttributes.target_temperature: 22.0,
            ACAttributes.indoor_temperature: 21.0,
            ACAttributes.fan_speed: 103,
            ACAttributes.swing_vertical: True,
            ACAttributes.swing_horizontal: True,
        },
    )
    entry = await _async_setup_entry(hass, device)
    entity_entry = _entity_entries(hass, entry)["123_climate"]

    assert (state := hass.states.get(entity_entry.entity_id))
    assert state.state == "unknown"


async def test_cf_temperature_range_attributes(hass: HomeAssistant) -> None:
    """Test CF min/max range attributes are exposed for low/high targets."""
    device = DummyDevice(
        DeviceType.CF,
        attributes={
            "power": True,
            "mode": 2,
            CFAttributes.min_temperature: 16,
            CFAttributes.max_temperature: 30,
            CFAttributes.current_temperature: 22,
        },
    )
    entry = await _async_setup_entry(hass, device)
    entity_entry = _entity_entries(hass, entry)["123_climate"]
    entity = hass.data[CLIMATE_DOMAIN].get_entity(entity_entry.entity_id)

    assert entity is not None
    assert entity.target_temperature_low == 16.0
    assert entity.target_temperature_high == 30.0


async def test_c3_temperature_fallback_and_turn_on(hass: HomeAssistant) -> None:
    """Test C3 fallback temperatures and turn_on path for zone power."""
    device = DummyDevice(
        DeviceType.C3,
        attributes={
            C3Attributes.zone_temp_type: [True],
            C3Attributes.temperature_min: [16],
            C3Attributes.temperature_max: [30],
            C3Attributes.mode: 1,
            C3Attributes.zone1_power: True,
            C3Attributes.target_temperature: [22],
            C3Attributes.temp_tw_in: [21.5],
        },
    )
    entry = await _async_setup_entry(hass, device)
    zone1 = _entity_entries(hass, entry)["123_climate_zone1"]
    entity = hass.data[CLIMATE_DOMAIN].get_entity(zone1.entity_id)

    assert entity is not None
    assert entity.target_temperature_low == 16.0
    assert entity.target_temperature_high == 30.0

    await _assert_service_calls(
        hass,
        zone1.entity_id,
        SERVICE_TURN_ON,
        {},
        [("set_attribute", C3Attributes.zone1_power, True)],
        device,
    )


async def test_fb_set_hvac_off_calls_turn_off(hass: HomeAssistant) -> None:
    """Test FB HVAC off delegates to turn_off."""
    device = DummyDevice(
        DeviceType.FB,
        attributes={
            FBAttributes.mode: "comfort",
            FBAttributes.power: True,
            FBAttributes.current_temperature: 20,
        },
    )
    entry = await _async_setup_entry(hass, device)
    entity_entry = _entity_entries(hass, entry)["123_climate"]

    await _assert_service_calls(
        hass,
        entity_entry.entity_id,
        SERVICE_SET_HVAC_MODE,
        {"hvac_mode": HVACMode.OFF},
        [("set_attribute", FBAttributes.power, False)],
        device,
    )


@pytest.mark.parametrize(
    ("device_type", "expected_count"),
    [
        pytest.param(DeviceType.AC, 1, id="ac"),
        pytest.param(DeviceType.CC, 1, id="cc"),
        pytest.param(DeviceType.CF, 1, id="cf"),
        pytest.param(DeviceType.C3, 2, id="c3"),
        pytest.param(DeviceType.FB, 1, id="fb"),
    ],
)
async def test_climate_async_setup_entry(
    hass: HomeAssistant,
    device_type: int,
    expected_count: int,
) -> None:
    """Test async_setup_entry creates the expected number of entities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**BASE_DATA, CONF_TYPE: device_type},
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.midea_lan.device_selector",
        return_value=DummyDevice(device_type),
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    entity_registry = er.async_get(hass)
    assert (
        len(er.async_entries_for_config_entry(entity_registry, entry.entry_id))
        == expected_count
    )


@pytest.mark.parametrize(
    "device",
    [
        pytest.param(
            DummyDevice(
                DeviceType.AC,
                attributes={
                    ACAttributes.power: True,
                    ACAttributes.mode: 1,
                    ACAttributes.target_temperature: 22.0,
                    ACAttributes.indoor_temperature: 21.0,
                    ACAttributes.comfort_mode: False,
                    ACAttributes.eco_mode: False,
                    ACAttributes.boost_mode: False,
                    ACAttributes.sleep_mode: False,
                    ACAttributes.frost_protect: False,
                    ACAttributes.fan_speed: 103,
                    ACAttributes.swing_vertical: True,
                    ACAttributes.swing_horizontal: True,
                    ACAttributes.indoor_humidity: 50,
                },
            ),
            id="ac",
        ),
    ],
)
async def test_climate_state_snapshot(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device: DummyDevice,
) -> None:
    """Snapshot climate entities for representative device types."""
    entry = await _async_setup_entry(hass, device)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
