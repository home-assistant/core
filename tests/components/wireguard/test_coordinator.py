"""Test the WireGuardUpdateCoordinator."""
from unittest.mock import MagicMock

from ha_wireguard_api.exceptions import (
    WireGuardException,
    WireGuardInvalidJson,
    WireGuardResponseError,
    WireGuardTimeoutError,
)
import pytest

from homeassistant.components.wireguard.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_coordinator_update_success(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    coordinator_client: MagicMock,
) -> None:
    """Test WireGuardUpdateCoordinator."""
    config_entry.add_to_hass(hass)
    coordinator_client.side_effect = None

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success


@pytest.mark.parametrize(
    ("side_effect", "message"),
    [
        (
            WireGuardTimeoutError,
            "Timeout occurred while connecting to WireGuard status API",
        ),
        (
            WireGuardResponseError,
            "Unexpected status from WireGuard status API",
        ),
        (
            WireGuardResponseError,
            "Unexpected content from WireGuard status API",
        ),
        (
            WireGuardInvalidJson,
            "Invalid JSON",
        ),
    ],
)
async def test_coordinator_update_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    coordinator_client: MagicMock,
    side_effect: WireGuardException,
    message: str,
) -> None:
    """Test WireGuardUpdateCoordinator."""
    config_entry.add_to_hass(hass)
    coordinator_client.get_peers.side_effect = side_effect(message)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    with pytest.raises(UpdateFailed) as exc:
        await coordinator._async_update_data()
        assert not coordinator.last_update_success
        assert message in str(exc)
