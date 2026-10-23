"""Tests for the button entities provided by the Lunatone integration."""

from unittest.mock import AsyncMock

from lunatone_rest_api_client.models import ScanState, StartScanData
import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import enable_entities, setup_integration


async def test_setup(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_sensors: AsyncMock,
    mock_lunatone_scan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Lunatone button setup."""
    await setup_integration(hass, mock_config_entry)
    await enable_entities(
        hass, entity_registry, mock_config_entry.entry_id, Platform.BUTTON
    )

    entities = hass.states.async_all(Platform.BUTTON)
    for entity_state in entities:
        entity_entry = entity_registry.async_get(entity_state.entity_id)
        assert entity_entry
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert entity_state == snapshot(name=f"{entity_entry.entity_id}-state")


async def test_pressing_button(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_sensors: AsyncMock,
    mock_lunatone_scan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test pressing button."""
    await setup_integration(hass, mock_config_entry)
    await enable_entities(
        hass, entity_registry, mock_config_entry.entry_id, Platform.BUTTON
    )

    async def fake_cancel() -> None:
        mock_lunatone_scan.data = mock_lunatone_scan.data.model_copy(
            update={"status": ScanState.NOT_STARTED}
        )

    async def fake_start(_: StartScanData) -> None:
        mock_lunatone_scan.data = mock_lunatone_scan.data.model_copy(
            update={"status": ScanState.IN_PROGRESS}
        )

    mock_lunatone_scan.async_cancel.side_effect = fake_cancel
    mock_lunatone_scan.async_start.side_effect = fake_start

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {
            ATTR_ENTITY_ID: "button.test_dali_scan_start_system_extension",
        },
        blocking=True,
    )
    mock_lunatone_scan.async_start.assert_awaited_with(
        StartScanData(newInstallation=False, noAddressing=False)
    )

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {
            ATTR_ENTITY_ID: "button.test_dali_scan_cancel",
        },
        blocking=True,
    )
    assert mock_lunatone_scan.async_cancel.await_count == 1

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {
            ATTR_ENTITY_ID: "button.test_dali_scan_start_new_installation",
        },
        blocking=True,
    )
    mock_lunatone_scan.async_start.assert_awaited_with(
        StartScanData(newInstallation=True, noAddressing=False)
    )

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {
            ATTR_ENTITY_ID: "button.test_dali_scan_cancel",
        },
        blocking=True,
    )
    assert mock_lunatone_scan.async_cancel.await_count == 2

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {
            ATTR_ENTITY_ID: "button.test_dali_scan_read_current_devices",
        },
        blocking=True,
    )
    mock_lunatone_scan.async_start.assert_awaited_with(
        StartScanData(newInstallation=False, noAddressing=True)
    )

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {
            ATTR_ENTITY_ID: "button.test_dali_scan_cancel",
        },
        blocking=True,
    )
    assert mock_lunatone_scan.async_cancel.await_count == 3

    with pytest.raises(
        HomeAssistantError,
        match="Cannot cancel DALI scan if it isn't running",
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: "button.test_dali_scan_cancel",
            },
            blocking=True,
        )
