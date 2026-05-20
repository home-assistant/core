"""Tests for the init module of the Easywave Core integration."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.easywave import (
    async_remove_config_entry_device,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.easywave.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from .conftest import (
    MOCK_ENTRY_DATA,
    MOCK_RECEIVER_SUBENTRY_ID,
    MOCK_TRANSMITTER_SUBENTRY_ID,
)

from tests.common import MockConfigEntry


def _patch_transceiver_and_coordinator() -> tuple[Any, Any, Any, Any]:
    """Return context managers patching RX11Transceiver and EasywaveCoordinator."""
    mock_transceiver = MagicMock()
    mock_coordinator = AsyncMock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()
    mock_coordinator.async_shutdown = AsyncMock()

    transceiver_patch = patch(
        "homeassistant.components.easywave.RX11Transceiver",
        return_value=mock_transceiver,
    )
    coordinator_patch = patch(
        "homeassistant.components.easywave.EasywaveCoordinator",
        return_value=mock_coordinator,
    )
    forward_patch = patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        return_value=None,
    )
    return transceiver_patch, coordinator_patch, forward_patch, mock_coordinator


async def test_setup_entry_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful setup of config entry."""
    mock_config_entry.add_to_hass(hass)
    hass.config.country = "DE"

    t_patch, c_patch, f_patch, mock_coord = _patch_transceiver_and_coordinator()
    with t_patch, c_patch, f_patch:
        result = await async_setup_entry(hass, mock_config_entry)

    assert result is True
    assert mock_coord.async_config_entry_first_refresh.called
    assert mock_config_entry.runtime_data.coordinator is mock_coord


async def test_setup_entry_country_allowed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup succeeds with allowed country."""
    mock_config_entry.add_to_hass(hass)
    hass.config.country = "FR"

    t_patch, c_patch, f_patch, _ = _patch_transceiver_and_coordinator()
    with t_patch, c_patch, f_patch:
        result = await async_setup_entry(hass, mock_config_entry)

    assert result is True


async def test_setup_entry_country_not_allowed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup returns False for disallowed country."""
    mock_config_entry.add_to_hass(hass)
    hass.config.country = "US"

    result = await async_setup_entry(hass, mock_config_entry)

    assert result is False


async def test_setup_entry_creates_repair_issue(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test repair issue created when country is not allowed."""
    mock_config_entry.add_to_hass(hass)
    hass.config.country = "US"

    result = await async_setup_entry(hass, mock_config_entry)

    assert result is False
    issues = ir.async_get(hass)
    issue = issues.async_get_issue(
        DOMAIN, f"frequency_not_permitted_{mock_config_entry.entry_id}"
    )
    assert issue is not None
    assert issue.translation_key == "frequency_not_permitted"


async def test_setup_entry_deletes_stale_repair_issue(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test stale repair issue is removed on successful setup."""
    mock_config_entry.add_to_hass(hass)
    hass.config.country = "DE"

    t_patch, c_patch, f_patch, _ = _patch_transceiver_and_coordinator()
    with t_patch, c_patch, f_patch:
        result = await async_setup_entry(hass, mock_config_entry)

    assert result is True
    issues = ir.async_get(hass)
    issue = issues.async_get_issue(
        DOMAIN, f"frequency_not_permitted_{mock_config_entry.entry_id}"
    )
    assert issue is None


async def test_setup_entry_no_country(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup succeeds when no country is configured."""
    mock_config_entry.add_to_hass(hass)
    hass.config.country = None

    t_patch, c_patch, f_patch, _ = _patch_transceiver_and_coordinator()
    with t_patch, c_patch, f_patch:
        result = await async_setup_entry(hass, mock_config_entry)

    assert result is True


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test unload of config entry shuts down coordinator."""
    mock_config_entry.add_to_hass(hass)
    hass.config.country = "DE"

    t_patch, c_patch, f_patch, mock_coord = _patch_transceiver_and_coordinator()
    with t_patch, c_patch, f_patch:
        await async_setup_entry(hass, mock_config_entry)

    with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
        result = await async_unload_entry(hass, mock_config_entry)

    assert result is True
    assert mock_coord.async_shutdown.called


async def test_remove_config_entry_device_rejects_gateway(
    hass: HomeAssistant,
) -> None:
    """Removing the RX11 gateway device must be denied."""
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        data=MOCK_ENTRY_DATA,
        unique_id="easywave_gw",
        options={"devices": []},
    )
    entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    gateway_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="RX11 USB Transceiver",
    )

    result = await async_remove_config_entry_device(hass, entry, gateway_device)
    assert result is False
    # Device list unchanged
    assert entry.options["devices"] == []


async def test_remove_config_entry_device_removes_child(
    hass: HomeAssistant,
) -> None:
    """Removing a child device via the three-dot menu should succeed and update options."""
    devices = [
        {"id": MOCK_RECEIVER_SUBENTRY_ID, "title": "Receiver", "data": {}},
        {"id": MOCK_TRANSMITTER_SUBENTRY_ID, "title": "Transmitter", "data": {}},
    ]
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        data=MOCK_ENTRY_DATA,
        unique_id="easywave_gw",
        options={"devices": devices},
    )
    entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    child_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, MOCK_RECEIVER_SUBENTRY_ID)},
        name="Receiver",
    )

    result = await async_remove_config_entry_device(hass, entry, child_device)
    assert result is True
    remaining = entry.options["devices"]
    assert len(remaining) == 1
    assert remaining[0]["id"] == MOCK_TRANSMITTER_SUBENTRY_ID
