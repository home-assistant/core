"""Tests for the Hot Spring sensor platform."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_with_selected_platforms

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_hotspring")
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the sensor platform state."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_hotspring")
@pytest.mark.parametrize(
    "entity_id",
    [
        "sensor.connectedspa_ddeeff_control_box_version",
        "sensor.connectedspa_ddeeff_wi_fi_dongle_version",
        "sensor.connectedspa_ddeeff_freshwater_salt_system_version",
    ],
)
async def test_disabled_by_default_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    entity_id: str,
) -> None:
    """Test the disabled by default Hot Spring sensors."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    assert hass.states.get(entity_id) is None

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


async def test_no_salt_cartridge(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
) -> None:
    """Test water care sensors are not added when cartridge is not installed."""
    mock_hotspring.update.return_value.water_care.cartridge_installed = False

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    assert hass.states.get("sensor.connectedspa_ddeeff_salt_cartridge_age") is None
    assert hass.states.get("sensor.connectedspa_ddeeff_salt_value") is None
    assert hass.states.get("sensor.connectedspa_ddeeff_salt_10_day_check_timer") is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_no_version_information(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
) -> None:
    """Test version sensors are not added when version string is empty."""
    mock_hotspring.update.return_value.versions.control_box = ""
    mock_hotspring.update.return_value.versions.wifi_dongle = ""
    mock_hotspring.update.return_value.versions.fwss = ""

    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    assert hass.states.get("sensor.connectedspa_ddeeff_control_box_version") is None
    assert hass.states.get("sensor.connectedspa_ddeeff_wi_fi_dongle_version") is None
    assert (
        hass.states.get("sensor.connectedspa_ddeeff_freshwater_salt_system_version")
        is None
    )
