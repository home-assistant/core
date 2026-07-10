"""Tests for the Bosch SHC sensor platform."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_integration

from tests.common import snapshot_platform


def _named(name: str) -> SimpleNamespace:
    """Build a minimal enum-like object exposing only .name, as boschshcpy enums do."""
    return SimpleNamespace(name=name)


def _base_device(device_id: str, name: str, **extra: Any) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        id=device_id,
        root_device_id="test-mac",
        serial=f"serial-{device_id}",
        device_services=[],
        manufacturer="Bosch",
        device_model="TEST",
        status="AVAILABLE",
        deleted=False,
        subscribe_callback=MagicMock(),
        unsubscribe_callback=MagicMock(),
        **extra,
    )


def _thermostat_device(
    device_id: str = "hdm:HomeMaticIP:thermostat1",
    temperature: float = 21.5,
    position: int = 42,
    valvestate: str = "OK",
) -> SimpleNamespace:
    return _base_device(
        device_id,
        "Thermostat",
        temperature=temperature,
        position=position,
        valvestate=_named(valvestate),
    )


def _wallthermostat_device(
    device_id: str = "hdm:HomeMaticIP:wallthermostat1",
    temperature: float = 20.0,
    humidity: float = 45.0,
) -> SimpleNamespace:
    return _base_device(
        device_id, "Wall Thermostat", temperature=temperature, humidity=humidity
    )


def _twinguard_device(
    device_id: str = "hdm:HomeMaticIP:twinguard1",
    temperature: float = 22.0,
    humidity: float = 50.0,
    purity: float = 500.0,
    combined_rating: str = "GOOD",
    description: str = "Air quality is good",
    temperature_rating: str = "GOOD",
    humidity_rating: str = "GOOD",
    purity_rating: str = "GOOD",
) -> SimpleNamespace:
    return _base_device(
        device_id,
        "Twinguard",
        temperature=temperature,
        humidity=humidity,
        purity=purity,
        combined_rating=_named(combined_rating),
        description=description,
        temperature_rating=_named(temperature_rating),
        humidity_rating=_named(humidity_rating),
        purity_rating=_named(purity_rating),
    )


def _smart_plug_device(
    device_id: str = "hdm:HomeMaticIP:plug1",
    powerconsumption: float = 12.5,
    energyconsumption: float = 3000.0,
) -> SimpleNamespace:
    return _base_device(
        device_id,
        "Smart Plug",
        powerconsumption=powerconsumption,
        energyconsumption=energyconsumption,
    )


def _light_switch_device(
    device_id: str = "hdm:HomeMaticIP:lightswitch1",
    powerconsumption: float = 6.0,
    energyconsumption: float = 900.0,
) -> SimpleNamespace:
    return _base_device(
        device_id,
        "Light Switch",
        powerconsumption=powerconsumption,
        energyconsumption=energyconsumption,
    )


def _smart_plug_compact_device(
    device_id: str = "hdm:HomeMaticIP:plugcompact1",
    powerconsumption: float = 8.0,
    energyconsumption: float = 1500.0,
    communicationquality: str = "GOOD",
) -> SimpleNamespace:
    return _base_device(
        device_id,
        "Smart Plug Compact",
        powerconsumption=powerconsumption,
        energyconsumption=energyconsumption,
        communicationquality=_named(communicationquality),
    )


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot every sensor entity the platform can create, across all 6 buckets."""
    entry = await setup_integration(
        hass,
        [Platform.SENSOR],
        thermostats=[_thermostat_device()],
        wallthermostats=[_wallthermostat_device()],
        twinguards=[_twinguard_device()],
        smart_plugs=[_smart_plug_device()],
        light_switches_bsm=[_light_switch_device()],
        smart_plugs_compact=[_smart_plug_compact_device()],
    )

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_setup_no_devices_adds_nothing(hass: HomeAssistant) -> None:
    """No devices in any bucket means no sensor entities are created."""
    await setup_integration(hass, [Platform.SENSOR])

    assert hass.states.async_all(SENSOR_DOMAIN) == []
