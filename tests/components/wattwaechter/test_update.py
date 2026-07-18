"""Tests for the WattWächter Plus update platform."""

from unittest.mock import AsyncMock, patch

from aio_wattwaechter import WattwaechterConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN, SERVICE_INSTALL
from homeassistant.components.wattwaechter.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_DEVICE_ID, MOCK_FW_VERSION

from tests.common import MockConfigEntry, snapshot_platform
from tests.typing import WebSocketGenerator


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test the firmware update entity."""
    with patch("homeassistant.components.wattwaechter.PLATFORMS", [Platform.UPDATE]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_install(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test installing a firmware update triggers ota_start."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id("update", DOMAIN, MOCK_DEVICE_ID)
    assert entity_id is not None

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_client.ota_start.assert_awaited_once()


async def test_install_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a rejected firmware update raises an error."""
    mock_client.ota_start.return_value = False

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id("update", DOMAIN, MOCK_DEVICE_ID)
    assert entity_id is not None

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


async def test_installed_version_falls_back_without_system_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the installed version falls back to the stored version."""
    mock_client.system_info.side_effect = WattwaechterConnectionError("offline")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id("update", DOMAIN, MOCK_DEVICE_ID)
    assert entity_id is not None
    assert hass.states.get(entity_id).attributes["installed_version"] == MOCK_FW_VERSION


async def test_release_notes(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the firmware release notes are exposed."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id("update", DOMAIN, MOCK_DEVICE_ID)
    assert entity_id is not None

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "update/release_notes", "entity_id": entity_id}
    )
    result = await client.receive_json()
    assert result["result"] == "Bug fixes and improvements"
