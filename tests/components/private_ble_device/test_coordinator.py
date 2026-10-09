"""Tests for the private_ble_device coordinator."""

import pytest

from homeassistant.core import HomeAssistant

from . import (
    DUMMY_IRK,
    MAC_RPA_VALID_1,
    MAC_STATIC,
    async_inject_broadcast,
    async_mock_config_entry,
    async_move_time_forwards,
)

from tests.components.bluetooth import _get_manager

OTHER_IRK = "11111111111111111111111111111111"


def _unavailable_callback_count(address: str) -> int:
    """Return how many non-connectable unavailable callbacks track an address."""
    # pylint: disable-next=protected-access
    return len(_get_manager()._unavailable_callbacks.get(address, ()))


@pytest.mark.usefixtures("enable_bluetooth")
async def test_ignored_address_unavailable_callback_released(
    hass: HomeAssistant,
) -> None:
    """Test an ignored address stops being tracked once it goes unavailable."""
    await async_mock_config_entry(hass)
    await async_inject_broadcast(hass, MAC_STATIC)
    assert _unavailable_callback_count(MAC_STATIC) == 1

    await async_move_time_forwards(hass, 910)
    assert _unavailable_callback_count(MAC_STATIC) == 0

    # Seen again after going away, it is ignored (and tracked) exactly once
    await async_inject_broadcast(hass, MAC_STATIC)
    assert _unavailable_callback_count(MAC_STATIC) == 1


@pytest.mark.usefixtures("enable_bluetooth")
async def test_ignored_address_released_when_irk_resolves(
    hass: HomeAssistant,
) -> None:
    """Test the ignore tracker is cancelled when a new IRK resolves the address."""
    await async_mock_config_entry(hass, OTHER_IRK)
    await async_inject_broadcast(hass, MAC_RPA_VALID_1)
    # Unresolvable by OTHER_IRK, so it is ignored
    assert _unavailable_callback_count(MAC_RPA_VALID_1) == 1

    await async_mock_config_entry(hass, DUMMY_IRK)
    # Only the resolved IRK's availability tracker remains
    assert _unavailable_callback_count(MAC_RPA_VALID_1) == 1
