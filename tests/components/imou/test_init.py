"""Tests for the Imou init."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.imou.const import DOMAIN, PARAM_MUTE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import create_online_device

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_imou_openapi_client", "mock_imou_ha_device_manager")
async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    init_integration: AsyncMock,
) -> None:
    """Test loading and unloading the config entry."""
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_imou_openapi_client", "mock_imou_ha_device_manager")
async def test_setup_entry_failed_on_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_imou_ha_device_manager: AsyncMock,
) -> None:
    """Device fetch failure during coordinator setup surfaces as setup retry."""
    mock_imou_ha_device_manager.async_get_devices.side_effect = RuntimeError(
        "Setup failed"
    )
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("init_integration")
async def test_device_registry_identifiers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Device registry uses channel-aware identifiers from the default mock devices."""
    registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(registry, mock_config_entry.entry_id)
    assert len(devices) == 1
    assert (DOMAIN, "d1") in devices[0].identifiers


@pytest.mark.parametrize(
    "imou_mock_devices",
    [
        [
            create_online_device(
                "dev-1",
                "Cam",
                channel_id="ch9",
                button_keys=(PARAM_MUTE,),
            ),
            create_online_device(
                "dev-1",
                "Cam",
                channel_id="ch10",
                button_keys=(PARAM_MUTE,),
            ),
        ]
    ],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_multiple_channels_create_separate_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Each channel gets its own device and button entities in the registries."""
    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    device_ids_by_key = {
        next(iter(device.identifiers))[1]: device.id for device in devices
    }
    assert set(device_ids_by_key) == {"dev-1_ch9", "dev-1_ch10"}

    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entries) == 2
    assert {entry.unique_id for entry in entries} == {
        "dev-1_ch9$mute",
        "dev-1_ch10$mute",
    }
    for entry in entries:
        assert entry.translation_key == PARAM_MUTE
        device_key = entry.unique_id.split("$", 1)[0]
        assert entry.device_id == device_ids_by_key[device_key]
