"""Tests for Daikin zone climate entities."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch
import urllib.parse

import pytest

from homeassistant.components.climate import HVACMode
from homeassistant.components.daikin import climate
from homeassistant.components.daikin.climate import (
    HA_STATE_TO_DAIKIN,
    DaikinZoneClimate,
    _async_set_zone_temperature,
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
        zone_settings_unavailable: bool = False,
        zone_param_ng: bool = False,
        raise_attr_on_get_zone_setting: int = 0,
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
        self._zone_settings_unavailable = zone_settings_unavailable
        self._zone_param_ng = zone_param_ng
        self._attr_errors_remaining = raise_attr_on_get_zone_setting
        self.values: dict[str, Any] = {
            "name": "Daikin Test",
            "model": "TESTMODEL",
            "ver": "1_0_0",
            "zone_name": ";".join(str(zone[0]) for zone in zones),
            "zone_onoff": ";".join(str(zone[1]) for zone in zones),
            "lztemp_h": ";".join(str(zone[2]) for zone in zones),
            "lztemp_c": ";".join(str(zone[2]) for zone in zones),
        }

    async def _get_resource(self, path: str):
        """Simulate zone endpoints."""
        if path.startswith("aircon/get_zone_setting"):
            if self._attr_errors_remaining > 0:
                self._attr_errors_remaining -= 1
                raise AttributeError("Simulated failure")
            if self._zone_settings_unavailable:
                return None
            return self.values
        if path.startswith("aircon/set_zone_setting"):
            if self._zone_param_ng:
                return "ret=PARAM NG"
            parsed = urllib.parse.urlparse(path)
            params = urllib.parse.parse_qs(parsed.query)
            lztemp_h = urllib.parse.unquote(params.get("lztemp_h", [""])[0])
            lztemp_c = urllib.parse.unquote(params.get("lztemp_c", [""])[0])
            if lztemp_h:
                self.values["lztemp_h"] = lztemp_h
            if lztemp_c:
                self.values["lztemp_c"] = lztemp_c
            return "ret=OK"
        return True

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
    """Setting the temperature updates both heating and cooling values."""
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


@pytest.mark.asyncio
async def test_async_set_zone_temperature_zone_inactive(hass: HomeAssistant) -> None:
    """Ensure inactive/configuration placeholder zones raise an error."""
    entry = MockConfigEntry(domain="daikin", data={})
    coordinator = DaikinCoordinator(
        hass,
        entry,
        FakeZoneDevice(zones=[["-", "0", 0]]),
    )

    with pytest.raises(HomeAssistantError) as err:
        await _async_set_zone_temperature(coordinator, 0, 21)

    assert err.value.translation_key == "zone_inactive"


@pytest.mark.asyncio
async def test_async_set_zone_temperature_zone_missing(hass: HomeAssistant) -> None:
    """Ensure missing zones raise the expected translation error."""
    entry = MockConfigEntry(domain="daikin", data={})
    coordinator = DaikinCoordinator(
        hass,
        entry,
        FakeZoneDevice(zones=[["Living", "1", 22]]),
    )

    with pytest.raises(HomeAssistantError) as err:
        await _async_set_zone_temperature(coordinator, 5, 21)

    assert err.value.translation_key == "zone_missing"


@pytest.mark.asyncio
async def test_async_set_zone_temperature_parameters_unavailable(
    hass: HomeAssistant,
) -> None:
    """Missing zone parameter lists should raise a descriptive error."""
    entry = MockConfigEntry(domain="daikin", data={})
    device = FakeZoneDevice(zones=[["Living", "1", 22]])
    device.values["lztemp_h"] = ""
    device.values["lztemp_c"] = ""
    coordinator = DaikinCoordinator(hass, entry, device)

    with pytest.raises(HomeAssistantError) as err:
        await _async_set_zone_temperature(coordinator, 0, 21)

    assert err.value.translation_key == "zone_parameters_unavailable"


@pytest.mark.asyncio
async def test_async_set_zone_temperature_settings_unavailable(
    hass: HomeAssistant,
) -> None:
    """Unavailable zone settings endpoint bubbles up as translated error."""
    entry = MockConfigEntry(domain="daikin", data={})
    coordinator = DaikinCoordinator(
        hass,
        entry,
        FakeZoneDevice(zones=[["Living", "1", 22]], zone_settings_unavailable=True),
    )

    with pytest.raises(HomeAssistantError) as err:
        await _async_set_zone_temperature(coordinator, 0, 21)

    assert err.value.translation_key == "zone_settings_unavailable"


@pytest.mark.asyncio
async def test_async_set_zone_temperature_param_ng(hass: HomeAssistant) -> None:
    """A PARAM NG response should raise the zone_set_failed message."""
    entry = MockConfigEntry(domain="daikin", data={})
    coordinator = DaikinCoordinator(
        hass,
        entry,
        FakeZoneDevice(zones=[["Living", "1", 22]], zone_param_ng=True),
    )

    with pytest.raises(HomeAssistantError) as err:
        await _async_set_zone_temperature(coordinator, 0, 21)

    assert err.value.translation_key == "zone_set_failed"


@pytest.mark.asyncio
async def test_async_set_zone_temperature_retry_limit(hass: HomeAssistant) -> None:
    """Attribute errors should trigger the retry limit handling."""
    entry = MockConfigEntry(domain="daikin", data={})
    coordinator = DaikinCoordinator(
        hass,
        entry,
        FakeZoneDevice(
            zones=[["Living", "1", 22]],
            raise_attr_on_get_zone_setting=3,
        ),
    )

    with pytest.raises(HomeAssistantError) as err:
        await _async_set_zone_temperature(coordinator, 0, 21)

    assert err.value.translation_key == "zone_set_retries_exceeded"


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
    """Zone climate exposes HVAC modes but does not allow changing them."""
    entry = MockConfigEntry(domain="daikin", data={})
    coordinator = DaikinCoordinator(
        hass,
        entry,
        FakeZoneDevice(zones=[["Living", "1", 22]]),
    )
    zone = DaikinZoneClimate(coordinator, 0)

    assert zone.hvac_modes == list(HA_STATE_TO_DAIKIN)

    with pytest.raises(HomeAssistantError) as err:
        await zone.async_set_hvac_mode(HVACMode.COOL)

    assert err.value.translation_key == "zone_hvac_read_only"
