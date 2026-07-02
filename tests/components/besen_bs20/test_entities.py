"""Tests for Besen BS20 Home Assistant entities."""

from collections.abc import Iterable
from types import SimpleNamespace
from typing import Any, cast

from besen_bs20.models import BesenBS20Data, ChargerConfig, ChargerInfo, ChargeStatus
import pytest

from homeassistant.components.besen_bs20 import (
    BesenBS20ConfigEntry,
    number as number_platform,
    select as select_platform,
    sensor as sensor_platform,
    switch as switch_platform,
    text as text_platform,
)
from homeassistant.components.besen_bs20.coordinator import BesenBS20Coordinator
from homeassistant.components.besen_bs20.entity import BesenBS20Entity
from homeassistant.components.besen_bs20.number import NUMBERS, BesenBS20Number
from homeassistant.components.besen_bs20.select import SELECTS, BesenBS20Select
from homeassistant.components.besen_bs20.sensor import SENSORS, BesenBS20Sensor
from homeassistant.components.besen_bs20.switch import BesenBS20ChargeSwitch
from homeassistant.components.besen_bs20.text import BesenBS20NameText
from homeassistant.helpers.entity_platform import AddEntitiesCallback


class _FakeClient:
    """Fake client exposed by a coordinator."""

    def __init__(self, state: BesenBS20Data) -> None:
        """Initialize the fake client."""

        self.address = state.info.address
        self.state = state


class _FakeCoordinator:
    """Fake coordinator with command methods used by entities."""

    def __init__(self, data: BesenBS20Data | None) -> None:
        """Initialize the fake coordinator."""

        fallback = data or BesenBS20Data(info=ChargerInfo(address="AA:BB"))
        self.data = data
        self.client = _FakeClient(fallback)
        self.calls: list[tuple[str, object | None]] = []

    async def async_start_charging(self) -> None:
        """Record charge start."""

        self.calls.append(("start", None))

    async def async_stop_charging(self) -> None:
        """Record charge stop."""

        self.calls.append(("stop", None))

    async def async_set_charge_amps(self, amps: int) -> None:
        """Record charge amp changes."""

        self.calls.append(("charge_amps", amps))

    async def async_set_lcd_brightness(self, brightness: int) -> None:
        """Record brightness changes."""

        self.calls.append(("lcd_brightness", brightness))

    async def async_set_temperature_unit(self, unit: str) -> None:
        """Record temperature-unit changes."""

        self.calls.append(("temperature_unit", unit))

    async def async_set_language(self, language: str) -> None:
        """Record language changes."""

        self.calls.append(("language", language))

    async def async_set_device_name(self, name: str) -> None:
        """Record device-name changes."""

        self.calls.append(("device_name", name))


def _state(*, phases: int = 3) -> BesenBS20Data:
    """Return a populated available charger state."""

    return BesenBS20Data(
        info=ChargerInfo(
            address="AA:BB",
            serial="SERIAL",
            phases=phases,
            manufacturer="Besen",
            model="BS20",
            hardware_version="HW1",
            software_version="SW1",
            output_max_amps=32,
        ),
        config=ChargerConfig(
            charge_amps=16,
            lcd_brightness=50,
            temperature_unit="Celcius",
            language="English",
            device_name="Garage",
            rssi=-55,
        ),
        charge=ChargeStatus(
            charger_status=True,
            current_energy=3500,
            total_energy=1.2,
            current_amount=12.3,
            inner_temp_c=24.5,
            l1_voltage=230.0,
            l1_amperage=15.2,
            plug_state="Connected Locked",
            output_state="Charging",
            current_state="Charging",
            error_details="No Error",
        ),
        available=True,
        authenticated=True,
    )


def _coordinator(data: BesenBS20Data | None = None) -> BesenBS20Coordinator:
    """Return a fake coordinator cast to the integration coordinator type."""

    return cast(BesenBS20Coordinator, _FakeCoordinator(data))


def _entry(coordinator: BesenBS20Coordinator) -> BesenBS20ConfigEntry:
    """Return a fake config entry with runtime data."""

    return cast(
        BesenBS20ConfigEntry,
        SimpleNamespace(runtime_data=SimpleNamespace(coordinator=coordinator)),
    )


def _collect_entities(entities: Iterable[Any], update_before_add: bool = False) -> None:
    """Collect entities from platform setup callbacks."""

    del update_before_add
    _ADDED.extend(entities)


_ADDED: list[Any] = []


def test_base_entity_device_info_and_availability() -> None:
    """Base entities expose device info and availability."""

    entity = BesenBS20Entity(_coordinator(_state()), "base")

    assert entity.available is True
    assert entity.unique_id == "AA:BB_base"
    assert entity.translation_key == "base"
    assert entity.device_info["name"] == "Garage"


@pytest.mark.asyncio
async def test_sensor_setup_filters_three_phase_entities() -> None:
    """One-phase chargers do not add L2/L3 sensors."""

    _ADDED.clear()
    await sensor_platform.async_setup_entry(
        cast(Any, object()),
        _entry(_coordinator(_state(phases=1))),
        cast(AddEntitiesCallback, _collect_entities),
    )

    keys = {entity.entity_description.key for entity in _ADDED}

    assert "l1_voltage" in keys
    assert "l2_voltage" not in keys
    assert "l3_current" not in keys


def test_sensor_values_options_and_availability() -> None:
    """Sensors expose values, enum options, and unavailable missing data."""

    coordinator = _coordinator(_state())
    power = BesenBS20Sensor(coordinator, SENSORS[0])
    error = BesenBS20Sensor(coordinator, SENSORS[11])
    missing = BesenBS20Sensor(_coordinator(None), SENSORS[0])

    assert power.native_value == 3500
    assert power.translation_key == "current_power"
    assert power.available is True
    assert "No Error" in cast(list[str], error.options)
    assert missing.available is False


@pytest.mark.asyncio
async def test_number_entities_expose_values_and_set_commands() -> None:
    """Number entities read values and dispatch coordinator commands."""

    coordinator = _coordinator(_state())
    charge_amps = BesenBS20Number(coordinator, NUMBERS[0])
    brightness = BesenBS20Number(coordinator, NUMBERS[1])

    assert charge_amps.native_value == 16
    assert charge_amps.native_max_value == 32

    await charge_amps.async_set_native_value(20)
    await brightness.async_set_native_value(75)

    fake = cast(_FakeCoordinator, coordinator)
    assert fake.calls == [("charge_amps", 20), ("lcd_brightness", 75)]


@pytest.mark.asyncio
async def test_select_text_and_switch_entities_dispatch_commands() -> None:
    """Select, text, and switch entities dispatch coordinator commands."""

    coordinator = _coordinator(_state())
    language = BesenBS20Select(coordinator, SELECTS[0])
    temperature = BesenBS20Select(coordinator, SELECTS[1])
    name = BesenBS20NameText(coordinator)
    charge = BesenBS20ChargeSwitch(coordinator)

    assert language.current_option == "English"
    assert language.translation_key == "language"
    assert "English" in language.options
    assert temperature.current_option == "Celcius"
    assert name.native_value == "Garage"
    assert name.translation_key == "device_name"
    assert charge.is_on is True
    assert charge.translation_key == "charging"

    await language.async_select_option("Deutsch")
    await temperature.async_select_option("Fahrenheit")
    await name.async_set_value("Driveway")
    await charge.async_turn_on()
    await charge.async_turn_off()

    fake = cast(_FakeCoordinator, coordinator)
    assert fake.calls == [
        ("language", "Deutsch"),
        ("temperature_unit", "Fahrenheit"),
        ("device_name", "Driveway"),
        ("start", None),
        ("stop", None),
    ]


@pytest.mark.asyncio
async def test_platform_setup_adds_control_entities() -> None:
    """Non-sensor platforms add their expected entities."""

    coordinator = _coordinator(_state())
    entry = _entry(coordinator)

    _ADDED.clear()
    add_entities = cast(AddEntitiesCallback, _collect_entities)

    await number_platform.async_setup_entry(cast(Any, object()), entry, add_entities)
    await select_platform.async_setup_entry(cast(Any, object()), entry, add_entities)
    await switch_platform.async_setup_entry(cast(Any, object()), entry, add_entities)
    await text_platform.async_setup_entry(cast(Any, object()), entry, add_entities)

    assert [type(entity) for entity in _ADDED] == [
        BesenBS20Number,
        BesenBS20Number,
        BesenBS20Select,
        BesenBS20Select,
        BesenBS20ChargeSwitch,
        BesenBS20NameText,
    ]
