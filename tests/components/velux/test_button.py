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
@pytest.mark.parametrize("mock_pyvlx", ["mock_window"], indirect=True)
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

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entity_entries) == 2

    # Check Reboot button is associated with the gateway device
    reboot_entry = next(
        e for e in entity_entries if e.entity_id == "button.klf_200_gateway_restart"
    )
    assert reboot_entry.device_id is not None
    gateway_device = device_registry.async_get(reboot_entry.device_id)
    assert gateway_device is not None
    assert (
        DOMAIN,
        f"gateway_{mock_config_entry.entry_id}",
    ) in gateway_device.identifiers
    assert gateway_device.via_device_id is None

    # Check Identify button is associated with the node device via the gateway
    identify_entry = next(
        e for e in entity_entries if e.entity_id == "button.test_window_identify"
    )
    assert identify_entry.device_id is not None
    node_device = device_registry.async_get(identify_entry.device_id)
    assert node_device is not None
    assert (DOMAIN, "123456789") in node_device.identifiers
    assert node_device.via_device_id == gateway_device.id


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


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize("mock_pyvlx", ["mock_window"], indirect=True)
async def test_identify_button_press_success(
    hass: HomeAssistant,
    mock_window: AsyncMock,
) -> None:
    """Test successful identify button press."""

    entity_id = "button.test_window_identify"

    # Press the button
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    # Verify the wink method was called
    mock_window.wink.assert_awaited_once()


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize("mock_pyvlx", ["mock_window"], indirect=True)
async def test_identify_button_press_failure(
    hass: HomeAssistant,
    mock_window: AsyncMock,
) -> None:
    """Test identify button press failure handling."""

    entity_id = "button.test_window_identify"

    # Mock wink failure
    mock_window.wink.side_effect = PyVLXException("Connection failed")

    # Press the button and expect HomeAssistantError
    with pytest.raises(
        HomeAssistantError,
        match='Failed to communicate with Velux device: <PyVLXException description="Connection failed" />',
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    # Verify the wink method was called
    mock_window.wink.assert_awaited_once()
