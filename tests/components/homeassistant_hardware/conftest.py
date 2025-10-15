"""Test fixtures for the Home Assistant Hardware integration."""

import asyncio
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.hassio import hostname_from_addon_slug
from homeassistant.components.otbr import OTBRData
from homeassistant.config_entries import (
    SIGNAL_CONFIG_ENTRY_CHANGED,
    ConfigEntryChange,
    ConfigEntryState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_zha_config_flow_setup() -> Generator[None]:
    """Mock the radio connection and probing of the ZHA config flow."""

    def mock_probe(config: dict[str, Any]) -> dict[str, Any]:
        # The radio probing will return the correct baudrate
        return {**config, "baudrate": 115200}

    mock_connect_app = MagicMock()
    mock_connect_app.__aenter__.return_value.backups.backups = [MagicMock()]
    mock_connect_app.__aenter__.return_value.backups.create_backup.return_value = (
        MagicMock()
    )

    with (
        patch(
            "bellows.zigbee.application.ControllerApplication.probe",
            side_effect=mock_probe,
        ),
        patch(
            "homeassistant.components.zha.radio_manager.ZhaRadioManager.create_zigpy_app",
            return_value=mock_connect_app,
        ),
        patch(
            "homeassistant.components.zha.async_setup_entry",
            return_value=True,
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def mock_zha_get_last_network_settings() -> Generator[None]:
    """Mock zha.api.async_get_last_network_settings."""

    with patch(
        "homeassistant.components.zha.api.async_get_last_network_settings",
        AsyncMock(return_value=None),
    ):
        yield


@pytest.fixture
def start_addon_with_otbr_discovery(
    hass: HomeAssistant, start_addon: AsyncMock
) -> AsyncMock:
    """Mock starting the OTBR addon and having hassio trigger OTBR discovery."""
    orig_start_addon_side_effect = start_addon.side_effect

    async def mock_addon_start(addon: str) -> None:
        """Create an OTBR config entry with runtime_data for dataset push testing."""
        await orig_start_addon_side_effect(addon)

        async def mock_otbr_hassio_discovery() -> None:
            # Discovery will happen a bit after the addon actually starts
            await asyncio.sleep(0.1)

            mock_otbr_data = MagicMock(spec=OTBRData)
            mock_otbr_data.set_active_dataset_tlvs = AsyncMock()
            mock_otbr_data.set_enabled = AsyncMock()

            # Create the config entry
            entry = MockConfigEntry(
                domain="otbr",
                data={"url": f"http://{hostname_from_addon_slug(addon)}:8081"},
                title="Open Thread Border Router",
                state=ConfigEntryState.LOADED,
            )
            entry.add_to_hass(hass)
            entry.runtime_data = mock_otbr_data

            # Manually trigger the signal that _push_dataset_to_otbr is waiting for
            async_dispatcher_send(
                hass, SIGNAL_CONFIG_ENTRY_CHANGED, ConfigEntryChange.ADDED, entry
            )

        # This runs asynchronously, after the addon has started
        hass.async_create_task(mock_otbr_hassio_discovery())

    start_addon.side_effect = mock_addon_start

    return start_addon
