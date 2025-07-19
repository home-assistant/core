"""Tests for the diagnostics data provided by the Sonos integration."""

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import paths

from homeassistant.components.sonos.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry

from tests.common import MockConfigEntry
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator


async def test_diagnostics_config_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    async_autosetup_sonos,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for config entry."""

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    # Exclude items that are timing dependent.
    assert result == snapshot(
        exclude=paths(
            "current_timestamp",
            "discovered.RINCON_test.event_stats.soco:from_didl_string",
            "discovered.RINCON_test.sonos_group_entities",
        )
    )


async def test_diagnostics_device(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: DeviceRegistry,
    async_autosetup_sonos,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for device."""

    TEST_DEVICE = "RINCON_test"

    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, TEST_DEVICE)})
    assert device_entry is not None

    result = await get_diagnostics_for_device(
        hass, hass_client, config_entry, device_entry
    )

    assert result == snapshot(
        exclude=paths(
            "event_stats.soco:from_didl_string",
            "sonos_group_entities",
        )
    )
