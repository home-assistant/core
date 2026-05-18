"""Tests for integration services and setup side effects."""

from unittest.mock import AsyncMock, patch

import pytest
from custom_components.fritzbox_vpn import (
    SERVICE_REGISTRATION_FLAG,
    _async_remove_unavailable_entities,
    _async_repair_entity_id_suffixes,
    async_setup,
    async_setup_entry,
)
from custom_components.fritzbox_vpn.const import (
    DOMAIN,
    SERVICE_REMOVE_UNAVAILABLE_ENTITIES,
    UNIQUE_ID_PREFIX,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.fixtures import MOCK_VPN_CONNECTIONS


@pytest.mark.asyncio
async def test_remove_unavailable_entities_service(
    hass: HomeAssistant, coordinator_with_data, mock_config_entry: MockConfigEntry
) -> None:
    """Service removes orphaned entities and reloads entry."""
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{UNIQUE_ID_PREFIX}orphan_switch",
        config_entry=mock_config_entry,
    )

    with patch.object(hass.config_entries, "async_reload", new=AsyncMock()) as reload_mock:
        await _async_remove_unavailable_entities(
            hass,
            type("Call", (), {"data": {"config_entry_id": mock_config_entry.entry_id}})(),
        )

    reload_mock.assert_awaited_once()
    remaining = er.async_entries_for_config_entry(registry, mock_config_entry.entry_id)
    assert all("orphan" not in (e.unique_id or "") for e in remaining)


@pytest.mark.asyncio
async def test_repair_entity_id_suffixes_service(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Service repairs suffixed entity IDs when configured."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "custom_components.fritzbox_vpn.entity_registry.repair_entity_id_suffixes",
        return_value=(0, []),
    ), patch.object(hass.config_entries, "async_reload", new=AsyncMock()):
        await _async_repair_entity_id_suffixes(
            hass,
            type("Call", (), {"data": {}})(),
        )


@pytest.mark.asyncio
async def test_services_registered_once(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Services are registered on first setup and removed on last unload."""
    await async_setup(hass, {})
    mock_config_entry.add_to_hass(hass)
    mock_coordinator = AsyncMock()
    mock_coordinator.data = MOCK_VPN_CONNECTIONS
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()
    mock_coordinator.fritz_session = AsyncMock()
    mock_coordinator.fritz_session.async_close = AsyncMock()

    with (
        patch(
            "custom_components.fritzbox_vpn.FritzBoxVPNCoordinator",
            return_value=mock_coordinator,
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(return_value=True),
        ),
    ):
        await async_setup_entry(hass, mock_config_entry)

    assert hass.services.has_service(DOMAIN, SERVICE_REMOVE_UNAVAILABLE_ENTITIES)
    assert hass.data[DOMAIN].get(SERVICE_REGISTRATION_FLAG)
