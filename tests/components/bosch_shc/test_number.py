"""Tests for the Bosch SHC number platform."""

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from homeassistant.components.bosch_shc.const import DOMAIN
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import make_device, setup_integration

from tests.common import MockConfigEntry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_AVAILABLE = "AVAILABLE"


def _avail(**attrs):
    """Shorthand: kwargs that make a device report as available."""
    return {"status": _AVAILABLE, **attrs}


# ---------------------------------------------------------------------------
# SHCNumber (offset) — lives in thermostats + roomthermostats
# ---------------------------------------------------------------------------


async def test_shc_number_offset_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """SHCNumber reports the device offset and dynamic min/max/step."""
    device = make_device(
        device_id="thermo-1",
        name="Thermostat 1",
        **_avail(
            offset=1.5,
            step_size=0.5,
            min_offset=-5.0,
            max_offset=5.0,
            async_set_offset=AsyncMock(),
        ),
    )
    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("number.thermostat_1_offset")
    assert state is not None
    assert state.state == "1.5"
    assert float(state.attributes["min"]) == -5.0
    assert float(state.attributes["max"]) == 5.0
    assert float(state.attributes["step"]) == 0.5


async def test_shc_number_offset_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """set_value calls async_set_offset with the supplied value."""
    device = make_device(
        device_id="thermo-1",
        name="Thermostat 1",
        **_avail(
            offset=0.0,
            step_size=0.5,
            min_offset=-5.0,
            max_offset=5.0,
            async_set_offset=AsyncMock(),
        ),
    )
    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        "set_value",
        {ATTR_ENTITY_ID: "number.thermostat_1_offset", "value": 2.0},
        blocking=True,
    )
    device.async_set_offset.assert_awaited_once_with(2.0)


async def test_shc_number_offset_clamped_to_max(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Values at the boundary are passed through unchanged (no over-clamp)."""
    device = make_device(
        device_id="thermo-1",
        name="Thermostat 1",
        **_avail(
            offset=0.0,
            step_size=0.5,
            min_offset=-5.0,
            max_offset=5.0,
            async_set_offset=AsyncMock(),
        ),
    )
    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        "set_value",
        {ATTR_ENTITY_ID: "number.thermostat_1_offset", "value": 5.0},
        blocking=True,
    )
    # value == max → passed straight through
    device.async_set_offset.assert_awaited_once_with(5.0)


async def test_shc_number_offset_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """TimeoutError from async_set_offset is re-raised as HomeAssistantError."""
    device = make_device(
        device_id="thermo-1",
        name="Thermostat 1",
        **_avail(
            offset=0.0,
            step_size=0.5,
            min_offset=-5.0,
            max_offset=5.0,
            async_set_offset=AsyncMock(side_effect=TimeoutError),
        ),
    )
    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            "set_value",
            {ATTR_ENTITY_ID: "number.thermostat_1_offset", "value": 1.0},
            blocking=True,
        )


async def test_shc_number_roomthermostat(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """SHCNumber is also created for roomthermostats."""
    device = make_device(
        device_id="roomthermo-1",
        name="Room Thermostat",
        **_avail(
            offset=-1.0,
            step_size=1.0,
            min_offset=-3.0,
            max_offset=3.0,
            async_set_offset=AsyncMock(),
        ),
    )
    mock_setup_dependencies.device_helper.roomthermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("number.room_thermostat_offset")
    assert state is not None
    assert state.state == "-1.0"


# ---------------------------------------------------------------------------
# ImpulseLengthNumber — lives in micromodule_impulse_relays
# ---------------------------------------------------------------------------


async def test_impulse_length_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """ImpulseLengthNumber converts lib tenths-of-seconds to seconds."""
    device = make_device(
        device_id="relay-1",
        name="Impulse Relay",
        **_avail(
            impulse_length=50,  # 50 tenths = 5 s
            async_set_impulse_length=AsyncMock(),
        ),
    )
    mock_setup_dependencies.device_helper.micromodule_impulse_relays = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("number.impulse_relay_impulse_length")
    assert state is not None
    assert state.state == "5.0"
    assert float(state.attributes["min"]) == 0.1
    assert float(state.attributes["max"]) == 60.0
    assert float(state.attributes["step"]) == 0.1


async def test_impulse_length_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """set_value converts seconds back to tenths-of-seconds (rounded int)."""
    device = make_device(
        device_id="relay-1",
        name="Impulse Relay",
        **_avail(
            impulse_length=10,
            async_set_impulse_length=AsyncMock(),
        ),
    )
    mock_setup_dependencies.device_helper.micromodule_impulse_relays = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        "set_value",
        {ATTR_ENTITY_ID: "number.impulse_relay_impulse_length", "value": 3.5},
        blocking=True,
    )
    # 3.5 s * 10 = 35 tenths
    device.async_set_impulse_length.assert_awaited_once_with(35)


async def test_impulse_length_none_skipped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Device with impulse_length=None is not added as an entity."""
    device = make_device(
        device_id="relay-2",
        name="Relay No Impulse",
        **_avail(impulse_length=None),
    )
    mock_setup_dependencies.device_helper.micromodule_impulse_relays = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("number.relay_no_impulse_impulse_length")
    assert state is None


async def test_impulse_length_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """KeyError from async_set_impulse_length is re-raised as HomeAssistantError."""
    device = make_device(
        device_id="relay-1",
        name="Impulse Relay",
        **_avail(
            impulse_length=10,
            async_set_impulse_length=AsyncMock(side_effect=KeyError("boom")),
        ),
    )
    mock_setup_dependencies.device_helper.micromodule_impulse_relays = [device]

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            "set_value",
            {ATTR_ENTITY_ID: "number.impulse_relay_impulse_length", "value": 1.0},
            blocking=True,
        )


# ---------------------------------------------------------------------------
# HeatingCircuitSetpointNumber — lives in heating_circuits
# ---------------------------------------------------------------------------


def _make_heating_circuit_device(device_id: str = "hc-1") -> MagicMock:
    """Build a mock HeatingCircuit device with service-backed setpoints."""
    svc = MagicMock()
    svc.setpoint_temperature_eco = 18.0
    svc.setpoint_temperature_comfort = 22.0

    device = make_device(device_id=device_id, name="Heating Circuit", status=_AVAILABLE)
    device._heating_circuit_service = svc
    device.async_set_setpoint_temperature_eco = AsyncMock()
    device.async_set_setpoint_temperature_comfort = AsyncMock()
    return device


async def test_heating_circuit_setpoint_eco_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """HeatingCircuitSetpointNumber reads eco setpoint from the private service."""
    device = _make_heating_circuit_device()
    mock_setup_dependencies.device_helper.heating_circuits = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("number.heating_circuit_setpoint_eco_temperature")
    assert state is not None
    assert state.state == "18.0"
    assert float(state.attributes["min"]) == 5.0
    assert float(state.attributes["max"]) == 30.0
    assert float(state.attributes["step"]) == 0.5


async def test_heating_circuit_setpoint_comfort_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """HeatingCircuitSetpointNumber reads comfort setpoint from the private service."""
    device = _make_heating_circuit_device()
    mock_setup_dependencies.device_helper.heating_circuits = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("number.heating_circuit_setpoint_comfort_temperature")
    assert state is not None
    assert state.state == "22.0"


async def test_heating_circuit_setpoint_eco_set(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """set_value calls async_set_setpoint_temperature_eco with clamped value."""
    device = _make_heating_circuit_device()
    mock_setup_dependencies.device_helper.heating_circuits = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        "set_value",
        {
            ATTR_ENTITY_ID: "number.heating_circuit_setpoint_eco_temperature",
            "value": 16.0,
        },
        blocking=True,
    )
    device.async_set_setpoint_temperature_eco.assert_awaited_once_with(16.0)


async def test_heating_circuit_setpoint_comfort_set(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """set_value calls async_set_setpoint_temperature_comfort."""
    device = _make_heating_circuit_device()
    mock_setup_dependencies.device_helper.heating_circuits = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        "set_value",
        {
            ATTR_ENTITY_ID: "number.heating_circuit_setpoint_comfort_temperature",
            "value": 21.5,
        },
        blocking=True,
    )
    device.async_set_setpoint_temperature_comfort.assert_awaited_once_with(21.5)


async def test_heating_circuit_setpoint_clamped_high(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Values at the max are passed unchanged."""
    device = _make_heating_circuit_device()
    mock_setup_dependencies.device_helper.heating_circuits = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        "set_value",
        {
            ATTR_ENTITY_ID: "number.heating_circuit_setpoint_eco_temperature",
            "value": 30.0,
        },
        blocking=True,
    )
    device.async_set_setpoint_temperature_eco.assert_awaited_once_with(30.0)


async def test_heating_circuit_setpoint_no_service(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """native_value returns None when _heating_circuit_service is None."""
    device = make_device(device_id="hc-2", name="HC No Service", status=_AVAILABLE)
    device._heating_circuit_service = None
    device.async_set_setpoint_temperature_eco = AsyncMock()
    device.async_set_setpoint_temperature_comfort = AsyncMock()
    mock_setup_dependencies.device_helper.heating_circuits = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("number.hc_no_service_setpoint_eco_temperature")
    assert state is not None
    assert state.state == "unknown"


async def test_heating_circuit_setpoint_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """TimeoutError from async_set_setpoint_temperature_eco raises HomeAssistantError."""
    device = _make_heating_circuit_device()
    device.async_set_setpoint_temperature_eco = AsyncMock(side_effect=TimeoutError)
    mock_setup_dependencies.device_helper.heating_circuits = [device]

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            "set_value",
            {
                ATTR_ENTITY_ID: "number.heating_circuit_setpoint_eco_temperature",
                "value": 17.0,
            },
            blocking=True,
        )


async def test_heating_circuit_setter_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """When async_set_<setter_name> is absent the method returns without raising."""
    device = make_device(device_id="hc-3", name="HC No Setter", status=_AVAILABLE)
    svc = MagicMock()
    svc.setpoint_temperature_eco = 20.0
    svc.setpoint_temperature_comfort = 22.0
    device._heating_circuit_service = svc
    # Explicitly remove the async setter so getattr returns None.
    device.async_set_setpoint_temperature_eco = None
    device.async_set_setpoint_temperature_comfort = AsyncMock()
    mock_setup_dependencies.device_helper.heating_circuits = [device]

    await setup_integration(hass, mock_config_entry)

    # Should NOT raise — the code logs a warning and returns early.
    await hass.services.async_call(
        NUMBER_DOMAIN,
        "set_value",
        {
            ATTR_ENTITY_ID: "number.hc_no_setter_setpoint_eco_temperature",
            "value": 18.0,
        },
        blocking=True,
    )


# ---------------------------------------------------------------------------
# PowerThresholdNumber — lives in smart_plugs / smart_plugs_compact
# ---------------------------------------------------------------------------


def _make_smart_plug(device_id: str = "plug-1", name: str = "Smart Plug") -> MagicMock:
    device = make_device(device_id=device_id, name=name, status=_AVAILABLE)
    device.supports_energy_saving_mode = True
    device.power_threshold = 50.0
    device.enter_duration_seconds = 120
    device.supports_led_brightness = False
    device.async_set_power_threshold = AsyncMock()
    device.async_set_enter_duration_seconds = AsyncMock()
    return device


async def test_power_threshold_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """PowerThresholdNumber reports the correct wattage state."""
    device = _make_smart_plug()
    mock_setup_dependencies.device_helper.smart_plugs = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("number.smart_plug_energy_saving_power_threshold")
    assert state is not None
    assert state.state == "50.0"
    assert float(state.attributes["min"]) == 0.0
    assert float(state.attributes["max"]) == 3680.0
    assert float(state.attributes["step"]) == 1.0


async def test_power_threshold_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """set_value calls async_set_power_threshold with clamped value."""
    device = _make_smart_plug()
    mock_setup_dependencies.device_helper.smart_plugs = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        "set_value",
        {
            ATTR_ENTITY_ID: "number.smart_plug_energy_saving_power_threshold",
            "value": 100.0,
        },
        blocking=True,
    )
    device.async_set_power_threshold.assert_awaited_once_with(100.0)


async def test_power_threshold_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """AttributeError from async_set_power_threshold raises HomeAssistantError."""
    device = _make_smart_plug()
    device.async_set_power_threshold = AsyncMock(side_effect=AttributeError("boom"))
    mock_setup_dependencies.device_helper.smart_plugs = [device]

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            "set_value",
            {
                ATTR_ENTITY_ID: "number.smart_plug_energy_saving_power_threshold",
                "value": 10.0,
            },
            blocking=True,
        )


async def test_power_threshold_compact_plug(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """PowerThresholdNumber is also created for smart_plugs_compact."""
    device = _make_smart_plug(device_id="plug-c", name="Compact Plug")
    mock_setup_dependencies.device_helper.smart_plugs_compact = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("number.compact_plug_energy_saving_power_threshold")
    assert state is not None


async def test_power_threshold_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Device without supports_energy_saving_mode gets no PowerThresholdNumber."""
    device = make_device(device_id="plug-ns", name="Plug No ESM", status=_AVAILABLE)
    device.supports_energy_saving_mode = False
    device.power_threshold = 50.0
    device.enter_duration_seconds = None
    device.supports_led_brightness = False
    mock_setup_dependencies.device_helper.smart_plugs = [device]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("number.plug_no_esm_energy_saving_power_threshold") is None


# ---------------------------------------------------------------------------
# EnterDurationNumber — lives in smart_plugs / smart_plugs_compact
# ---------------------------------------------------------------------------


async def test_enter_duration_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """EnterDurationNumber converts the integer seconds to float."""
    device = _make_smart_plug()
    mock_setup_dependencies.device_helper.smart_plugs = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("number.smart_plug_energy_saving_enter_duration")
    assert state is not None
    assert state.state == "120.0"
    assert float(state.attributes["min"]) == 1.0
    assert float(state.attributes["max"]) == 3600.0
    assert float(state.attributes["step"]) == 1.0


async def test_enter_duration_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """set_value calls async_set_enter_duration_seconds as int."""
    device = _make_smart_plug()
    mock_setup_dependencies.device_helper.smart_plugs = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        "set_value",
        {
            ATTR_ENTITY_ID: "number.smart_plug_energy_saving_enter_duration",
            "value": 300.0,
        },
        blocking=True,
    )
    device.async_set_enter_duration_seconds.assert_awaited_once_with(300)


async def test_enter_duration_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """TimeoutError from async_set_enter_duration_seconds raises HomeAssistantError."""
    device = _make_smart_plug()
    device.async_set_enter_duration_seconds = AsyncMock(side_effect=TimeoutError)
    mock_setup_dependencies.device_helper.smart_plugs = [device]

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            "set_value",
            {
                ATTR_ENTITY_ID: "number.smart_plug_energy_saving_enter_duration",
                "value": 60.0,
            },
            blocking=True,
        )


# ---------------------------------------------------------------------------
# LedBrightnessNumber — lives in smart_plugs / smart_plugs_compact
# ---------------------------------------------------------------------------


def _make_led_plug(device_id: str = "led-plug-1", name: str = "LED Plug") -> MagicMock:
    """Build a smart plug mock that supports LED brightness."""
    led_svc = MagicMock()
    led_svc.min_brightness = 0
    led_svc.max_brightness = 100
    led_svc.step_size = 10

    device = make_device(device_id=device_id, name=name, status=_AVAILABLE)
    device.supports_energy_saving_mode = False
    device.power_threshold = None
    device.enter_duration_seconds = None
    device.supports_led_brightness = True
    device.led_brightness = 60.0
    device._led_brightness_configuration_service = led_svc
    device.async_set_led_brightness = AsyncMock()
    return device


async def test_led_brightness_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """LedBrightnessNumber reads min/max/step from the private service."""
    device = _make_led_plug()
    mock_setup_dependencies.device_helper.smart_plugs = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("number.led_plug_led_brightness")
    assert state is not None
    assert state.state == "60.0"
    assert float(state.attributes["min"]) == 0.0
    assert float(state.attributes["max"]) == 100.0
    assert float(state.attributes["step"]) == 10.0


async def test_led_brightness_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """set_value calls async_set_led_brightness with the requested float."""
    device = _make_led_plug()
    mock_setup_dependencies.device_helper.smart_plugs = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        "set_value",
        {ATTR_ENTITY_ID: "number.led_plug_led_brightness", "value": 80.0},
        blocking=True,
    )
    device.async_set_led_brightness.assert_awaited_once_with(80.0)


async def test_led_brightness_service_fallback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """When _led_brightness_configuration_service is None, fallback to 0/100/1."""
    device = _make_led_plug()
    device._led_brightness_configuration_service = None
    mock_setup_dependencies.device_helper.smart_plugs = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("number.led_plug_led_brightness")
    assert state is not None
    assert float(state.attributes["min"]) == 0.0
    assert float(state.attributes["max"]) == 100.0
    assert float(state.attributes["step"]) == 1.0


async def test_led_brightness_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """aiohttp.ClientError from async_set_led_brightness raises HomeAssistantError."""
    device = _make_led_plug()
    device.async_set_led_brightness = AsyncMock(
        side_effect=aiohttp.ClientError("network fail")
    )
    mock_setup_dependencies.device_helper.smart_plugs = [device]

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            "set_value",
            {ATTR_ENTITY_ID: "number.led_plug_led_brightness", "value": 50.0},
            blocking=True,
        )


# ---------------------------------------------------------------------------
# DisplayBrightnessNumber — lives in thermostats + roomthermostats
# ---------------------------------------------------------------------------


def _make_display_device(
    device_id: str = "disp-1", name: str = "Display Thermo"
) -> MagicMock:
    """Build a thermostat-like mock with display config support."""
    disp_svc = MagicMock()
    disp_svc.display_brightness_min = 0
    disp_svc.display_brightness_max = 10
    disp_svc.display_brightness_step_size = 1
    disp_svc.display_on_time_min = 5
    disp_svc.display_on_time_max = 30
    disp_svc.display_on_time_step_size = 5

    device = make_device(device_id=device_id, name=name, status=_AVAILABLE)
    device.offset = 0.0
    device.step_size = 0.5
    device.min_offset = -5.0
    device.max_offset = 5.0
    device.async_set_offset = AsyncMock()
    device.supports_display_configuration = True
    device.display_brightness = 5.0
    device.display_on_time = 10.0
    device._display_config_service = disp_svc
    device.async_set_display_brightness = AsyncMock()
    device.async_set_display_on_time = AsyncMock()
    return device


async def test_display_brightness_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """DisplayBrightnessNumber reads bounds from _display_config_service."""
    device = _make_display_device()
    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("number.display_thermo_display_brightness")
    assert state is not None
    assert state.state == "5.0"
    assert float(state.attributes["min"]) == 0.0
    assert float(state.attributes["max"]) == 10.0
    assert float(state.attributes["step"]) == 1.0


async def test_display_brightness_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """set_value calls async_set_display_brightness with the float value."""
    device = _make_display_device()
    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        "set_value",
        {ATTR_ENTITY_ID: "number.display_thermo_display_brightness", "value": 8.0},
        blocking=True,
    )
    device.async_set_display_brightness.assert_awaited_once_with(8.0)


async def test_display_brightness_service_fallback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """When _display_config_service is None, fallback min=0, max=100, step=1."""
    device = _make_display_device()
    device._display_config_service = None
    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("number.display_thermo_display_brightness")
    assert state is not None
    assert float(state.attributes["min"]) == 0.0
    assert float(state.attributes["max"]) == 100.0
    assert float(state.attributes["step"]) == 1.0


async def test_display_brightness_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """TimeoutError from async_set_display_brightness raises HomeAssistantError."""
    device = _make_display_device()
    device.async_set_display_brightness = AsyncMock(side_effect=TimeoutError)
    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            "set_value",
            {
                ATTR_ENTITY_ID: "number.display_thermo_display_brightness",
                "value": 3.0,
            },
            blocking=True,
        )


# ---------------------------------------------------------------------------
# DisplayOnTimeNumber — lives in thermostats + roomthermostats
# ---------------------------------------------------------------------------


async def test_display_on_time_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """DisplayOnTimeNumber reads bounds from _display_config_service."""
    device = _make_display_device()
    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("number.display_thermo_display_on_time")
    assert state is not None
    assert state.state == "10.0"
    assert float(state.attributes["min"]) == 5.0
    assert float(state.attributes["max"]) == 30.0
    assert float(state.attributes["step"]) == 5.0


async def test_display_on_time_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """set_value calls async_set_display_on_time."""
    device = _make_display_device()
    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        "set_value",
        {ATTR_ENTITY_ID: "number.display_thermo_display_on_time", "value": 20.0},
        blocking=True,
    )
    device.async_set_display_on_time.assert_awaited_once_with(20.0)


async def test_display_on_time_service_fallback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """When _display_config_service is None, fallback min=0, max=3600, step=1."""
    device = _make_display_device()
    device._display_config_service = None
    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("number.display_thermo_display_on_time")
    assert state is not None
    assert float(state.attributes["min"]) == 0.0
    assert float(state.attributes["max"]) == 3600.0
    assert float(state.attributes["step"]) == 1.0


async def test_display_on_time_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """KeyError from async_set_display_on_time raises HomeAssistantError."""
    device = _make_display_device()
    device.async_set_display_on_time = AsyncMock(side_effect=KeyError("gone"))
    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            "set_value",
            {ATTR_ENTITY_ID: "number.display_thermo_display_on_time", "value": 15.0},
            blocking=True,
        )


async def test_heating_circuit_setpoint_native_value_attribute_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """native_value returns None when the service getter raises AttributeError."""

    class _BrokenSvc:
        """Service stub whose eco getter raises AttributeError."""

        @property
        def setpoint_temperature_eco(self):
            raise AttributeError("gone")

        setpoint_temperature_comfort = 22.0

    device = make_device(device_id="hc-err", name="HC Attr Error", status=_AVAILABLE)
    device._heating_circuit_service = _BrokenSvc()
    device.async_set_setpoint_temperature_eco = AsyncMock()
    device.async_set_setpoint_temperature_comfort = AsyncMock()
    mock_setup_dependencies.device_helper.heating_circuits = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("number.hc_attr_error_setpoint_eco_temperature")
    assert state is not None
    assert state.state == "unknown"


async def test_shc_number_excluded_thermostat(
    hass: HomeAssistant,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Excluded thermostat device does not produce a SHCNumber entity."""
    device = make_device(
        device_id="excl-thermo",
        name="Excluded Thermo",
        **_avail(
            offset=0.0,
            step_size=0.5,
            min_offset=-5.0,
            max_offset=5.0,
            async_set_offset=AsyncMock(),
        ),
    )
    mock_setup_dependencies.device_helper.thermostats = [device]

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="shc012345",
        unique_id="test-mac",
        entry_id="01JE69BM3MA48YE6RH05A4MDKQ",
        data={
            "host": "1.1.1.1",
            "ssl_certificate": "/etc/bosch_shc/test-cert.pem",
            "ssl_key": "/etc/bosch_shc/test-key.pem",
            "token": "abc:test-mac",
            "hostname": "test-mac",
        },
        options={"excluded_devices": ["excl-thermo"]},
    )
    await setup_integration(hass, entry)

    assert hass.states.get("number.excluded_thermo_offset") is None


async def test_impulse_length_excluded_relay(
    hass: HomeAssistant,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Excluded impulse relay does not produce an ImpulseLengthNumber entity."""
    device = make_device(
        device_id="excl-relay",
        name="Excluded Relay",
        **_avail(
            impulse_length=50,
            async_set_impulse_length=AsyncMock(),
        ),
    )
    mock_setup_dependencies.device_helper.micromodule_impulse_relays = [device]

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="shc012345",
        unique_id="test-mac",
        entry_id="01JE69BM3MA48YE6RH05A4MDKQ",
        data={
            "host": "1.1.1.1",
            "ssl_certificate": "/etc/bosch_shc/test-cert.pem",
            "ssl_key": "/etc/bosch_shc/test-key.pem",
            "token": "abc:test-mac",
            "hostname": "test-mac",
        },
        options={"excluded_devices": ["excl-relay"]},
    )
    await setup_integration(hass, entry)

    assert hass.states.get("number.excluded_relay_impulse_length") is None


async def test_impulse_length_no_attr_skipped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Device without impulse_length attribute at all is skipped (hasattr guard)."""
    device = MagicMock(spec=["id", "name", "serial", "root_device_id",
                               "device_model", "manufacturer", "deleted",
                               "device_services", "room_id", "status",
                               "subscribe_callback", "unsubscribe_callback"])
    device.id = "relay-noattr"
    device.name = "Relay No Attr"
    device.serial = "relay-noattr"
    device.root_device_id = "shc-root"
    device.device_model = "TEST_MODEL"
    device.manufacturer = "BOSCH"
    device.deleted = False
    device.device_services = []
    device.room_id = "room-1"
    device.status = _AVAILABLE
    # impulse_length intentionally absent from spec
    mock_setup_dependencies.device_helper.micromodule_impulse_relays = [device]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("number.relay_no_attr_impulse_length") is None


async def test_display_on_time_none_not_added(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Thermostat with display_on_time=None gets no DisplayOnTimeNumber entity."""
    device = make_device(device_id="thermo-nd", name="Thermo No Display", status=_AVAILABLE)
    device.offset = 0.0
    device.step_size = 0.5
    device.min_offset = -5.0
    device.max_offset = 5.0
    device.async_set_offset = AsyncMock()
    device.supports_display_configuration = True
    device.display_brightness = 5.0
    device.display_on_time = None  # triggers the guard
    device._display_config_service = MagicMock()
    device.async_set_display_brightness = AsyncMock()
    mock_setup_dependencies.device_helper.thermostats = [device]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("number.thermo_no_display_display_on_time") is None
    # brightness entity should still exist (display_brightness is not None)
    assert hass.states.get("number.thermo_no_display_display_brightness") is not None
