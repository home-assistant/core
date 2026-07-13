"""bosch_shc session fixtures."""

from __future__ import annotations

from collections.abc import Generator
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.bosch_shc.const import (
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    DOMAIN,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def bosch_shc_mock_async_zeroconf(mock_async_zeroconf: MagicMock) -> None:
    """Auto mock zeroconf."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock bosch_shc config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_SSL_CERTIFICATE: "cert",
            CONF_SSL_KEY: "key",
        },
        unique_id="test-mac",
    )


# Keep in sync with every platform's device_helper buckets — a bucket
# missing here breaks the mock_session fixture for whichever test needs it.
_EMPTY_DEVICE_BUCKETS: dict[str, list[Any]] = {
    bucket: []
    for bucket in (
        "camera_360",
        "camera_eyes",
        "light_switches_bsm",
        "motion_detectors",
        "shutter_contacts",
        "shutter_contacts2",
        "shutter_controls",
        "smart_plugs",
        "smart_plugs_compact",
        "smoke_detectors",
        "thermostats",
        "twinguards",
        "universal_switches",
        "wallthermostats",
        "water_leakage_detectors",
    )
}


@pytest.fixture
def device_buckets(request: pytest.FixtureRequest) -> dict[str, list[Any]]:
    """device_helper buckets for the mock session.

    Empty by default; a test overrides specific buckets via
    ``@pytest.mark.parametrize("device_buckets", [{...}], indirect=True)``.
    """
    overrides: dict[str, list[Any]] = getattr(request, "param", {})
    return {**_EMPTY_DEVICE_BUCKETS, **overrides}


@pytest.fixture
def mock_session(device_buckets: dict[str, list[Any]]) -> Generator[MagicMock]:
    """Mock SHCSession, patched in for the duration of the test."""
    session = MagicMock()
    session.information.unique_id = "test-mac"
    session.information.updateState.name = "UP_TO_DATE"
    session.information.version = "2.0"
    session.device_helper = SimpleNamespace(**device_buckets)
    with patch("homeassistant.components.bosch_shc.SHCSession", return_value=session):
        yield session


async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the bosch_shc integration for testing."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


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


def thermostat_device(
    device_id: str = "hdm:HomeMaticIP:thermostat1",
    temperature: float = 21.5,
    position: int = 42,
    valvestate: str = "OK",
) -> SimpleNamespace:
    """Build a minimal thermostat device double."""
    return _base_device(
        device_id,
        "Thermostat",
        temperature=temperature,
        position=position,
        valvestate=_named(valvestate),
    )


def wallthermostat_device(
    device_id: str = "hdm:HomeMaticIP:wallthermostat1",
    temperature: float = 20.0,
    humidity: float = 45.0,
) -> SimpleNamespace:
    """Build a minimal wall-thermostat device double."""
    return _base_device(
        device_id, "Wall Thermostat", temperature=temperature, humidity=humidity
    )


def twinguard_device(
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
    """Build a minimal Twinguard device double."""
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


def smart_plug_device(
    device_id: str = "hdm:HomeMaticIP:plug1",
    powerconsumption: float = 12.5,
    energyconsumption: float = 3000.0,
) -> SimpleNamespace:
    """Build a minimal smart-plug device double."""
    return _base_device(
        device_id,
        "Smart Plug",
        powerconsumption=powerconsumption,
        energyconsumption=energyconsumption,
    )


def light_switch_device(
    device_id: str = "hdm:HomeMaticIP:lightswitch1",
    powerconsumption: float = 6.0,
    energyconsumption: float = 900.0,
) -> SimpleNamespace:
    """Build a minimal light-switch (BSM) device double."""
    return _base_device(
        device_id,
        "Light Switch",
        powerconsumption=powerconsumption,
        energyconsumption=energyconsumption,
    )


def smart_plug_compact_device(
    device_id: str = "hdm:HomeMaticIP:plugcompact1",
    powerconsumption: float = 8.0,
    energyconsumption: float = 1500.0,
    communicationquality: str = "GOOD",
) -> SimpleNamespace:
    """Build a minimal Smart Plug Compact device double."""
    return _base_device(
        device_id,
        "Smart Plug Compact",
        powerconsumption=powerconsumption,
        energyconsumption=energyconsumption,
        communicationquality=_named(communicationquality),
    )
