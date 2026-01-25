"""Tests for Daikin zone climate entities."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
import urllib.parse

import pytest

from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.components.daikin import climate
from homeassistant.components.daikin.climate import (
    DaikinZoneClimate,
    _supports_zone_temperature_control,
    _system_target_temperature,
    _zone_temperature_from_list,
    _zone_temperature_lists,
)
from homeassistant.components.daikin.coordinator import DaikinCoordinator
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from tests.common import MockConfigEntry


class FakeZoneDevice:
    """Fake Daikin device exposing zone temperature control."""

    def __init__(
        self,
        *,
        zones: list[list[str | int]],
        target_temperature: float = 22,
        mode: str = "hot",
    ) -> None:
        """Initialize the fake zone-capable device."""
        self.mac = "00:11:22:33:44:55"
        self.target_temperature = target_temperature
        self.zones = zones
        self.fan_rate: list[str] = []
        self.swing_modes: list[str] = []
        self.support_away_mode = False
        self.support_advanced_modes = False
        self.support_fan_rate = False
        self.support_swing_mode = False
        self.support_compressor_frequency = False
        self.compressor_frequency = 0
        self.inside_temperature = 21
        self._mode = mode
        self.values: dict[str, Any] = {
            "name": "Daikin Test",
            "model": "TESTMODEL",
            "ver": "1_0_0",
            "zone_name": ";".join(str(zone[0]) for zone in zones),
            "zone_onoff": ";".join(str(zone[1]) for zone in zones),
            "lztemp_h": ";".join(str(zone[2]) for zone in zones),
            "lztemp_c": ";".join(str(zone[2]) for zone in zones),
        }

    async def set_zone(self, zone_id: int, key: str, value: str) -> None:
        """Simulate setting a zone value."""
        if key not in {"zone_onoff", "lztemp_h", "lztemp_c"}:
            raise KeyError(key)

        if key == "zone_onoff":
            current = self.values.get("zone_onoff", "")
            zones = current.split(";") if current else []
            zones[zone_id] = str(value)
            self.values["zone_onoff"] = ";".join(zones)
            return

        current = self.represent(key)[1]
        current[zone_id] = str(value)
        self.values[key] = ";".join(current)

    def represent(self, key: str) -> tuple[None, list[str] | str]:
        """Return decoded data for the requested key."""
        if key == "lztemp_h":
            decoded = urllib.parse.unquote(self.values["lztemp_h"])
            return (None, decoded.split(";") if decoded else [])
        if key == "lztemp_c":
            decoded = urllib.parse.unquote(self.values["lztemp_c"])
            return (None, decoded.split(";") if decoded else [])
        if key == "mode":
            return (None, self._mode)
        if key in ("f_rate", "f_dir", "en_hol", "adv", "htemp", "otemp", "stemp"):
            return (None, "")
        return (None, "")

    async def update_status(self) -> None:
        """Simulate a status refresh."""


def test_zone_temperature_helpers() -> None:
    """Helpers return expected defaults and fallbacks."""

    class NoRepresent:
        """Device without represent method."""

    assert _zone_temperature_lists(NoRepresent()) == ([], [])
    assert _zone_temperature_from_list(["1"], 5) is None
    assert _zone_temperature_from_list(["bad"], 0) is None
    assert _zone_temperature_from_list(["21.5"], 0) == 21.5

    class BadTemperature:
        """Device with invalid target temperature."""

        target_temperature = "bad"

    assert _system_target_temperature(BadTemperature()) is None


def test_supports_zone_temperature_control() -> None:
    """Zone temperature control requires zones and matching lists."""

    class DeviceNoZones:
        """Device without zones."""

        zones = None

    assert not _supports_zone_temperature_control(DeviceNoZones())

    device_ok = SimpleNamespace(
        zones=[["Zone 1", "1", 22]],
        represent=lambda key: (None, ["21"] if key == "lztemp_h" else ["22"]),
    )
    assert _supports_zone_temperature_control(device_ok)

    device_short = SimpleNamespace(
        zones=[["Zone 1", "1", 22], ["Zone 2", "1", 20]],
        represent=lambda key: (None, ["21"] if key == "lztemp_h" else ["22"]),
    )
    assert not _supports_zone_temperature_control(device_short)


@pytest.mark.asyncio
async def test_async_setup_entry_adds_zone_climates(hass: HomeAssistant) -> None:
    """Zone climates are added when the controller exposes temperatures."""
    entry = MockConfigEntry(domain="daikin", data={})
    device = FakeZoneDevice(
        zones=[["-", "0", 0], ["Living", "1", 22], ["Office", "1", 21]]
    )
    entry.runtime_data = SimpleNamespace(device=device)
    added_entities: list = []

    def _async_add_entities(entities) -> None:
        """Collect entities added during setup."""
        added_entities.extend(entities)

    with (
        patch(
            "homeassistant.components.daikin.climate.DaikinClimate", autospec=True
        ) as main_climate,
        patch(
            "homeassistant.components.daikin.climate.DaikinZoneClimate", autospec=True
        ) as zone_climate,
    ):
        await climate.async_setup_entry(hass, entry, _async_add_entities)

    assert len(added_entities) == 3
    assert main_climate.call_count == 1
    # Only two configured zones should create climates
    assert zone_climate.call_count == 2
    zone_ids = [call.args[1] for call in zone_climate.call_args_list]
    assert zone_ids == [1, 2]


@pytest.mark.asyncio
async def test_async_setup_entry_skips_zone_climates_without_support(
    hass: HomeAssistant,
) -> None:
    """No zone climates are created when zone temperatures are missing."""
    entry = MockConfigEntry(domain="daikin", data={})
    device = FakeZoneDevice(zones=[["Living", "1", 22]])
    device.values["lztemp_h"] = ""
    device.values["lztemp_c"] = ""
    entry.runtime_data = SimpleNamespace(device=device)

    def _async_add_entities(_entities) -> None:
        """No-op entity adder used for validation."""

    with (
        patch("homeassistant.components.daikin.climate.DaikinClimate", autospec=True),
        patch(
            "homeassistant.components.daikin.climate.DaikinZoneClimate", autospec=True
        ) as zone_climate,
    ):
        await climate.async_setup_entry(hass, entry, _async_add_entities)

    zone_climate.assert_not_called()


@pytest.mark.asyncio
async def test_zone_climate_sets_temperature(hass: HomeAssistant) -> None:
    """Setting the temperature updates the active mode value."""
    entry = MockConfigEntry(domain="daikin", data={})
    coordinator = DaikinCoordinator(
        hass,
        entry,
        FakeZoneDevice(zones=[["Living", "1", 22], ["Office", "1", 21]]),
    )
    # Avoid scheduling real refresh work in the test environment
    coordinator.async_request_refresh = AsyncMock()
    zone = DaikinZoneClimate(coordinator, 0)

    await zone.async_set_temperature(**{ATTR_TEMPERATURE: 23})

    heating = coordinator.device.represent("lztemp_h")[1]
    cooling = coordinator.device.represent("lztemp_c")[1]
    assert heating[0] == "23"
    assert cooling[0] == "22"


@pytest.mark.asyncio
async def test_zone_climate_sets_temperature_cooling(
    hass: HomeAssistant,
) -> None:
    """Setting the temperature updates the cooling list when in cool mode."""
    entry = MockConfigEntry(domain="daikin", data={})
    coordinator = DaikinCoordinator(
        hass,
        entry,
        FakeZoneDevice(
            zones=[["Living", "1", 22], ["Office", "1", 21]],
            mode="cool",
        ),
    )
    # Avoid scheduling real refresh work in the test environment
    coordinator.async_request_refresh = AsyncMock()
    zone = DaikinZoneClimate(coordinator, 0)

    await zone.async_set_temperature(**{ATTR_TEMPERATURE: 23})

    heating = coordinator.device.represent("lztemp_h")[1]
    cooling = coordinator.device.represent("lztemp_c")[1]
    assert heating[0] == "22"
    assert cooling[0] == "23"


@pytest.mark.asyncio
async def test_zone_climate_rejects_out_of_range_temperature(
    hass: HomeAssistant,
) -> None:
    """Values outside the ±2°C window raise HomeAssistantError."""
    entry = MockConfigEntry(domain="daikin", data={})
    coordinator = DaikinCoordinator(
        hass,
        entry,
        FakeZoneDevice(zones=[["Living", "1", 22]], target_temperature=22),
    )
    zone = DaikinZoneClimate(coordinator, 0)

    with pytest.raises(HomeAssistantError) as err:
        await zone.async_set_temperature(**{ATTR_TEMPERATURE: 30})

    assert err.value.translation_key == "temperature_out_of_range"


@pytest.mark.asyncio
async def test_zone_climate_keeps_zone_disabled(hass: HomeAssistant) -> None:
    """Updating temperature on a disabled zone should not turn it on."""
    entry = MockConfigEntry(domain="daikin", data={})
    coordinator = DaikinCoordinator(
        hass,
        entry,
        FakeZoneDevice(zones=[["Living", "0", 22]]),
    )
    zone = DaikinZoneClimate(coordinator, 0)

    await zone.async_set_temperature(**{ATTR_TEMPERATURE: 21})

    assert coordinator.device.values["zone_onoff"] == "0"
    assert zone.target_temperature == 21.0


@pytest.mark.asyncio
async def test_zone_climate_available_when_zone_disabled(hass: HomeAssistant) -> None:
    """Ensure zone climate stays available even if the physical zone is off."""
    entry = MockConfigEntry(domain="daikin", data={})
    coordinator = DaikinCoordinator(
        hass,
        entry,
        FakeZoneDevice(zones=[["Living", "0", 22]]),
    )
    zone = DaikinZoneClimate(coordinator, 0)
    assert zone.available


def test_zone_climate_unavailable_without_target_temperature(
    hass: HomeAssistant,
) -> None:
    """Ensure zone climate is unavailable if target temperature is missing."""
    entry = MockConfigEntry(domain="daikin", data={})
    device = FakeZoneDevice(zones=[["Living", "1", 22]])
    device.target_temperature = None
    coordinator = DaikinCoordinator(hass, entry, device)
    zone = DaikinZoneClimate(coordinator, 0)

    assert not zone.available


@pytest.mark.asyncio
async def test_zone_climate_zone_inactive(hass: HomeAssistant) -> None:
    """Ensure inactive/configuration placeholder zones raise an error."""
    entry = MockConfigEntry(domain="daikin", data={})
    coordinator = DaikinCoordinator(
        hass,
        entry,
        FakeZoneDevice(zones=[["-", "0", 0]]),
    )
    zone = DaikinZoneClimate(coordinator, 0)

    with pytest.raises(HomeAssistantError) as err:
        await zone.async_set_temperature(**{ATTR_TEMPERATURE: 21})

    assert err.value.translation_key == "zone_inactive"


@pytest.mark.asyncio
async def test_zone_climate_zone_missing(hass: HomeAssistant) -> None:
    """Ensure missing zones raise the expected translation error."""
    entry = MockConfigEntry(domain="daikin", data={})
    coordinator = DaikinCoordinator(
        hass,
        entry,
        FakeZoneDevice(zones=[["Living", "1", 22], ["Office", "1", 22]]),
    )
    zone = DaikinZoneClimate(coordinator, 1)
    coordinator.device.zones = [["Living", "1", 22]]

    with pytest.raises(HomeAssistantError) as err:
        await zone.async_set_temperature(**{ATTR_TEMPERATURE: 21})

    assert err.value.translation_key == "zone_missing"


@pytest.mark.asyncio
async def test_zone_climate_parameters_unavailable(hass: HomeAssistant) -> None:
    """Missing zone parameter lists should raise a descriptive error."""
    entry = MockConfigEntry(domain="daikin", data={})
    device = FakeZoneDevice(zones=[["Living", "1", 22]])
    device.values["lztemp_h"] = ""
    device.values["lztemp_c"] = ""
    coordinator = DaikinCoordinator(hass, entry, device)
    zone = DaikinZoneClimate(coordinator, 0)

    with pytest.raises(HomeAssistantError) as err:
        await zone.async_set_temperature(**{ATTR_TEMPERATURE: 21})

    assert err.value.translation_key == "zone_parameters_unavailable"


@pytest.mark.asyncio
async def test_zone_climate_requires_temperature(hass: HomeAssistant) -> None:
    """Missing temperature payloads raise a translated validation error."""
    entry = MockConfigEntry(domain="daikin", data={})
    coordinator = DaikinCoordinator(
        hass,
        entry,
        FakeZoneDevice(zones=[["Living", "1", 22]]),
    )
    zone = DaikinZoneClimate(coordinator, 0)

    with pytest.raises(ServiceValidationError) as err:
        await zone.async_set_temperature()

    assert err.value.translation_key == "zone_temperature_missing"


@pytest.mark.asyncio
async def test_zone_climate_hvac_modes_read_only(hass: HomeAssistant) -> None:
    """Zone climate exposes current HVAC mode but does not allow changing it."""
    entry = MockConfigEntry(domain="daikin", data={})
    coordinator = DaikinCoordinator(
        hass,
        entry,
        FakeZoneDevice(zones=[["Living", "1", 22]]),
    )
    zone = DaikinZoneClimate(coordinator, 0)

    assert zone.hvac_modes == [zone.hvac_mode]

    with pytest.raises(HomeAssistantError) as err:
        await zone.async_set_hvac_mode(HVACMode.COOL)

    assert err.value.translation_key == "zone_hvac_read_only"


def test_zone_climate_properties(hass: HomeAssistant) -> None:
    """Expose zone climate properties for current mode and limits."""
    entry = MockConfigEntry(domain="daikin", data={})
    device = FakeZoneDevice(
        zones=[["Living", "1", 22]],
        target_temperature=24,
        mode="cool",
    )
    device.values["lztemp_h"] = "20"
    device.values["lztemp_c"] = "18"
    coordinator = DaikinCoordinator(hass, entry, device)
    zone = DaikinZoneClimate(coordinator, 0)

    assert zone.hvac_action == HVACAction.COOLING
    assert zone.target_temperature == 18.0
    assert zone.min_temp == 22.0
    assert zone.max_temp == 26.0
    assert zone.extra_state_attributes == {"zone_id": 0}


def test_zone_climate_target_temperature_inactive_mode(hass: HomeAssistant) -> None:
    """Return no target temperature when not heating or cooling."""
    entry = MockConfigEntry(domain="daikin", data={})
    device = FakeZoneDevice(
        zones=[["Living", "1", 22]],
        mode="auto",
    )
    device.values["lztemp_h"] = "bad"
    device.values["lztemp_c"] = "19"
    coordinator = DaikinCoordinator(hass, entry, device)
    zone = DaikinZoneClimate(coordinator, 0)

    assert zone.target_temperature is None


@pytest.mark.asyncio
async def test_zone_climate_set_zone_failed(hass: HomeAssistant) -> None:
    """Surface errors when zone temperature updates fail."""
    entry = MockConfigEntry(domain="daikin", data={})
    device = FakeZoneDevice(zones=[["Living", "1", 22]])
    device.set_zone = AsyncMock(side_effect=NotImplementedError)
    coordinator = DaikinCoordinator(hass, entry, device)
    zone = DaikinZoneClimate(coordinator, 0)

    with pytest.raises(HomeAssistantError) as err:
        await zone.async_set_temperature(**{ATTR_TEMPERATURE: 21})

    assert err.value.translation_key == "zone_set_failed"
