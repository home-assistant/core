"""Test Velux button entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pyvlx import PyVLXException
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.velux import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platform() -> Platform:
    """Fixture to specify platform to test."""
    return Platform.BUTTON


@pytest.mark.usefixtures("setup_integration")
async def test_button_snapshot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the button entity (registry + state)."""
    await snapshot_platform(
        hass,
        entity_registry,
        snapshot,
        mock_config_entry.entry_id,
    )

    # Get the button entity setup and test device association
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entity_entries) == 1
    entry = entity_entries[0]

    assert entry.device_id is not None
    device_entry = device_registry.async_get(entry.device_id)
    assert device_entry is not None
    assert (DOMAIN, f"gateway_{mock_config_entry.entry_id}") in device_entry.identifiers
    assert device_entry.via_device_id is None


@pytest.mark.usefixtures("setup_integration")
async def test_button_press_success(
    hass: HomeAssistant,
    mock_pyvlx: MagicMock,
) -> None:
    """Test successful button press."""

    # Configure the mock method to be async and return a coroutine
    mock_pyvlx.reboot_gateway.return_value = AsyncMock()()

    # Press the button
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.klf_200_gateway_restart"},
        blocking=True,
    )

    # Verify the reboot method was called
    mock_pyvlx.reboot_gateway.assert_called_once()


@pytest.mark.usefixtures("setup_integration")
async def test_button_press_failure(
    hass: HomeAssistant,
    mock_pyvlx: MagicMock,
) -> None:
    """Test button press failure handling."""

    # Mock reboot failure
    mock_pyvlx.reboot_gateway.side_effect = PyVLXException("Connection failed")

    # Press the button and expect HomeAssistantError
    with pytest.raises(
        HomeAssistantError,
        match="Failed to reboot gateway. Try again in a few moments or power cycle the device manually",
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.klf_200_gateway_restart"},
            blocking=True,
        )

    # Verify the reboot method was called
    mock_pyvlx.reboot_gateway.assert_called_once()
