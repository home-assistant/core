"""Tests for Imou diagnostics."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyimouapi.exceptions import ImouException
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.imou.coordinator import SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Diagnostics include the region, App ID, and current devices."""
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
        == snapshot
    )


async def test_diagnostics_reports_open_api_quota(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A used-up monthly quota is visible in diagnostics and clears after a later poll."""
    mock_imou_ha_device_manager.async_get_devices.side_effect = ImouException(
        "OP1013 monthly quota exceeded"
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    )
    assert diagnostics["coordinator"]["open_api_quota_exceeded"] is True

    mock_imou_ha_device_manager.async_get_devices.side_effect = None
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    )
    assert diagnostics["coordinator"]["open_api_quota_exceeded"] is False
