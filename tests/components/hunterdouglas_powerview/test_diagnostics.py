"""Test the Hunter Douglas Powerview diagnostics."""

from typing import Any

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.hunterdouglas_powerview.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import MOCK_SERIAL

EXCLUDE_PROPS = props("device_id", "id", "via_device_id")


def _sort_entities(device: dict[str, Any]) -> None:
    """Sort a device's entities, as platforms are set up concurrently."""
    device["entities"].sort(key=lambda entity: entity["entity_id"])


@pytest.mark.freeze_time("2026-01-01T00:00:00+00:00")
@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize("api_version", [1])
async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    diagnostics["device_info"].sort(key=lambda device: device["name"])
    for device in diagnostics["device_info"]:
        _sort_entities(device)
    assert diagnostics == snapshot(exclude=EXCLUDE_PROPS)


@pytest.mark.freeze_time("2026-01-01T00:00:00+00:00")
@pytest.mark.usefixtures("mock_hunterdouglas_hub")
@pytest.mark.parametrize(
    ("api_version", "device_identifier"),
    [
        pytest.param(1, MOCK_SERIAL, id="hub"),
        pytest.param(1, 36492, id="gen1_shade"),
        pytest.param(2, 13542, id="gen2_shade"),
    ],
)
async def test_device_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    device_identifier: str | int,
) -> None:
    """Test generating diagnostics for a hub and for a shade device."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, device_identifier), mock_config_entry.entry_id
    )
    assert device is not None

    diagnostics = await get_diagnostics_for_device(
        hass, hass_client, mock_config_entry, device
    )

    _sort_entities(diagnostics["device_info"])
    assert diagnostics == snapshot(exclude=EXCLUDE_PROPS)
