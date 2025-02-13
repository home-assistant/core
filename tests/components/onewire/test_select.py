"""Tests for 1-Wire selects."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.onewire.onewirehub import _DEVICE_SCAN_INTERVAL
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_owproxy_mock_devices
from .const import MOCK_OWPROXY_DEVICES

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture(autouse=True)
def override_platforms() -> Generator[None]:
    """Override PLATFORMS."""
    with patch("homeassistant.components.onewire._PLATFORMS", [Platform.SELECT]):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_selects(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    owproxy: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test for 1-Wire select entities."""
    setup_owproxy_mock_devices(owproxy, MOCK_OWPROXY_DEVICES.keys())
    await hass.config_entries.async_setup(config_entry.entry_id)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize("device_id", ["28.111111111111"])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_selects_delayed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    owproxy: MagicMock,
    device_id: str,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test for delayed 1-Wire select entities."""
    setup_owproxy_mock_devices(owproxy, [])
    await hass.config_entries.async_setup(config_entry.entry_id)

    assert not er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)

    setup_owproxy_mock_devices(owproxy, [device_id])
    freezer.tick(_DEVICE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        len(er.async_entries_for_config_entry(entity_registry, config_entry.entry_id))
        == 1
    )


@pytest.mark.parametrize("device_id", ["28.111111111111"])
async def test_selection_option_service(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    owproxy: MagicMock,
    device_id: str,
) -> None:
    """Test for 1-Wire select option service."""
    setup_owproxy_mock_devices(owproxy, [device_id])
    await hass.config_entries.async_setup(config_entry.entry_id)

    entity_id = "select.28_111111111111_temperature_resolution"
    assert hass.states.get(entity_id).state == "12"

    # Test SELECT_OPTION service
    owproxy.return_value.read.side_effect = [b"         9"]
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "9"},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == "9"
