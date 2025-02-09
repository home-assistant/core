"""Tests for the HEOS diagnostics module."""

from unittest import mock

from pyheos import HeosSystem
import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.heos.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import MockHeos

from tests.common import MockConfigEntry
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator


async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    controller: MockHeos,
    system: HeosSystem,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    with mock.patch.object(
        controller, controller.get_system_info.__name__, return_value=system
    ):
        diagnostics = await get_diagnostics_for_config_entry(
            hass, hass_client, config_entry
        )

    assert diagnostics == snapshot(
        exclude=props("created_at", "modified_at", "entry_id")
    )


@pytest.mark.usefixtures("controller")
async def test_config_entry_diagnostics_error_getting_system(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics with error during getting system info."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    # Not patching get_system_info to raise error 'Not connected to device'

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    assert diagnostics == snapshot(
        exclude=props("created_at", "modified_at", "entry_id")
    )


@pytest.mark.usefixtures("controller")
async def test_device_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device({(DOMAIN, "1")})
    assert device is not None
    diagnostics = await get_diagnostics_for_device(
        hass, hass_client, config_entry, device
    )
    assert diagnostics == snapshot(
        exclude=props(
            "created_at",
            "modified_at",
            "config_entries",
            "id",
            "primary_config_entry",
            "config_entry_id",
            "device_id",
            "entity_picture_local",
            "last_changed",
            "last_reported",
            "last_updated",
        )
    )
