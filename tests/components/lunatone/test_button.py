"""Tests for the button entities provided by the Lunatone integration."""

from copy import deepcopy
from unittest.mock import AsyncMock

import aiohttp
from freezegun.api import FrozenDateTimeFactory
from lunatone_rest_api_client.models import (
    ScanLineData,
    ScanLineState,
    ScanState,
    StartScanData,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.lunatone.const import DOMAIN
from homeassistant.components.lunatone.coordinator import DEFAULT_INFO_UPDATE_INTERVAL
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


async def test_pressing_button_handles_connection_error(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_sensors: AsyncMock,
    mock_lunatone_scan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test pressing a scan button handles connection errors."""
    await setup_integration(hass, mock_config_entry)
    await enable_entities(
        hass, entity_registry, mock_config_entry.entry_id, Platform.BUTTON
    )

    mock_lunatone_scan.async_start.side_effect = aiohttp.ClientConnectionError()

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: "button.test_dali_scan_start_system_extension",
            },
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "cannot_control_dali_scan"
    assert err.value.translation_placeholders == {
        "entity": "button.test_dali_scan_start_system_extension"
    }
    assert isinstance(err.value.__cause__, aiohttp.ClientConnectionError)


async def test_cancel_scan_uses_refreshed_scan_state(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_sensors: AsyncMock,
    mock_lunatone_scan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test canceling a scan uses the latest scan state."""
    await setup_integration(hass, mock_config_entry)
    await enable_entities(
        hass, entity_registry, mock_config_entry.entry_id, Platform.BUTTON
    )

    async def fake_update() -> None:
        mock_lunatone_scan.data = mock_lunatone_scan.data.model_copy(
            update={"status": ScanState.IN_PROGRESS}
        )

    mock_lunatone_scan.async_update.side_effect = fake_update

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_dali_scan_cancel"},
        blocking=True,
    )

    mock_lunatone_scan.async_cancel.assert_awaited_once()


async def test_cancel_scan_aborts_when_refresh_fails(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_sensors: AsyncMock,
    mock_lunatone_scan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test canceling a scan aborts if its state cannot be refreshed."""
    await setup_integration(hass, mock_config_entry)
    await enable_entities(
        hass, entity_registry, mock_config_entry.entry_id, Platform.BUTTON
    )

    mock_lunatone_scan.async_update.side_effect = aiohttp.ClientConnectionError()

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.test_dali_scan_cancel"},
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "cannot_retrieve_scan_data"
    mock_lunatone_scan.async_cancel.assert_not_awaited()


@pytest.mark.parametrize("line_id", [0, 1])
@pytest.mark.parametrize(
    ("entity_suffix", "new_installation", "no_addressing"),
    [
        ("start_system_extension", False, False),
        ("start_new_installation", True, False),
        ("read_current_devices", False, True),
    ],
)
async def test_pressing_line_scan_button(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_sensors: AsyncMock,
    mock_lunatone_scan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    line_id: int,
    entity_suffix: str,
    new_installation: bool,
    no_addressing: bool,
) -> None:
    """Test pressing line-specific scan buttons selects the line."""
    await setup_integration(hass, mock_config_entry)
    await enable_entities(
        hass, entity_registry, mock_config_entry.entry_id, Platform.BUTTON
    )

    scan_update_count = mock_lunatone_scan.async_update.await_count

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: (f"button.dali_line_{line_id}_dali_scan_{entity_suffix}")},
        blocking=True,
    )

    mock_lunatone_scan.async_start.assert_awaited_once_with(
        StartScanData(
            newInstallation=new_installation,
            noAddressing=no_addressing,
            useLines=[line_id],
        )
    )
    assert mock_lunatone_scan.async_update.await_count == scan_update_count + 1


@pytest.mark.parametrize("line_id", [0, 1])
async def test_line_scan_button_busy_target(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_sensors: AsyncMock,
    mock_lunatone_scan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    line_id: int,
) -> None:
    """Test a line-specific scan button rejects a busy target line."""
    await setup_integration(hass, mock_config_entry)
    await enable_entities(
        hass, entity_registry, mock_config_entry.entry_id, Platform.BUTTON
    )

    mock_lunatone_scan.data = mock_lunatone_scan.data.model_copy(
        update={
            "lines": [
                ScanLineData(
                    line=line,
                    scanState=(
                        ScanLineState.SCANNING
                        if line == line_id
                        else ScanLineState.IDLE
                    ),
                )
                for line in (0, 1)
            ]
        }
    )

    with pytest.raises(
        HomeAssistantError,
        match="Cannot start a new DALI scan if it is already running",
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: (
                    f"button.dali_line_{line_id}_dali_scan_start_system_extension"
                )
            },
            blocking=True,
        )

    mock_lunatone_scan.async_start.assert_not_awaited()


@pytest.mark.parametrize("line_id", [0, 1])
async def test_line_scan_button_idle_target_when_another_line_busy(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_sensors: AsyncMock,
    mock_lunatone_scan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    line_id: int,
) -> None:
    """Test an idle target line can scan while another line is busy."""
    await setup_integration(hass, mock_config_entry)
    await enable_entities(
        hass, entity_registry, mock_config_entry.entry_id, Platform.BUTTON
    )

    busy_line = 1 - line_id
    mock_lunatone_scan.data = mock_lunatone_scan.data.model_copy(
        update={
            "lines": [
                ScanLineData(
                    line=line,
                    scanState=(
                        ScanLineState.SCANNING
                        if line == busy_line
                        else ScanLineState.IDLE
                    ),
                )
                for line in (0, 1)
            ]
        }
    )

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {
            ATTR_ENTITY_ID: (
                f"button.dali_line_{line_id}_dali_scan_start_system_extension"
            )
        },
        blocking=True,
    )

    mock_lunatone_scan.async_start.assert_awaited_once_with(
        StartScanData(
            newInstallation=False,
            noAddressing=False,
            useLines=[line_id],
        )
    )


async def test_line_buttons_added_and_removed(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_sensors: AsyncMock,
    mock_lunatone_scan: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test line-specific buttons are added and removed with their line."""
    await setup_integration(hass, mock_config_entry)

    updated_info_data = deepcopy(mock_lunatone_info.data)
    updated_info_data.lines["2"] = updated_info_data.lines["1"]
    mock_lunatone_info.data = updated_info_data

    freezer.tick(DEFAULT_INFO_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.unique_id is not None
    unique_ids = (
        f"{mock_config_entry.unique_id}-line2-scan",
        f"{mock_config_entry.unique_id}-line2-scan-new",
        f"{mock_config_entry.unique_id}-line2-scan-current",
    )
    line_button_entity_ids = [
        entity_registry.async_get_entity_id(Platform.BUTTON, DOMAIN, unique_id)
        for unique_id in unique_ids
    ]
    assert all(line_button_entity_ids)

    del updated_info_data.lines["2"]
    mock_lunatone_info.data = updated_info_data

    freezer.tick(DEFAULT_INFO_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    for unique_id in unique_ids:
        assert (
            entity_registry.async_get_entity_id(Platform.BUTTON, DOMAIN, unique_id)
            is None
        )
