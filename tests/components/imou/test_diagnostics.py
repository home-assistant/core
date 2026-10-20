"""Tests for Imou diagnostics."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pyimouapi.exceptions import ImouException, InvalidAppIdOrSecretException
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.imou.coordinator import SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


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


async def test_diagnostics_reports_quota_from_status_refresh(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A quota error while refreshing status is visible in diagnostics."""
    mock_imou_ha_device_manager.async_update_devices_status.side_effect = ImouException(
        "OP1013:monthly quota exceeded"
    )
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    last_exception = init_integration.runtime_data.last_exception
    assert isinstance(last_exception, HomeAssistantError)
    assert last_exception.translation_key == "quota_exceeded"
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    )
    assert diagnostics["coordinator"]["open_api_quota_exceeded"] is True


@pytest.mark.parametrize(
    ("api_name", "follow_up"),
    [
        ("async_get_devices", TimeoutError()),
        ("async_get_devices", InvalidAppIdOrSecretException("bad credentials")),
        ("async_get_devices", ImouException("cloud failure")),
        ("async_update_devices_status", TimeoutError()),
        (
            "async_update_devices_status",
            InvalidAppIdOrSecretException("bad credentials"),
        ),
        ("async_update_devices_status", ImouException("cloud failure")),
    ],
)
async def test_quota_flag_clears_when_a_later_poll_is_not_quota(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    mock_imou_ha_device_manager: MagicMock,
    freezer: FrozenDateTimeFactory,
    api_name: str,
    follow_up: Exception,
) -> None:
    """Timeout, auth, and other cloud errors clear a previous quota flag."""
    api = getattr(mock_imou_ha_device_manager, api_name)
    api.side_effect = ImouException("OP1013:monthly quota exceeded")
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    api.side_effect = follow_up
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    )
    assert diagnostics["coordinator"]["open_api_quota_exceeded"] is False
