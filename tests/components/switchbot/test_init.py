"""Test the switchbot init."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.switchbot import async_setup_entry
from homeassistant.components.switchbot.const import (
    CONF_ENCRYPTION_KEY,
    CONF_KEY_ID,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SENSOR_TYPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.setup import async_setup_component

from . import (
    WOHAND_SERVICE_INFO,
    WOMETERTHPC_SERVICE_INFO,
    WORELAY_SWITCH_1PM_SERVICE_INFO,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_setup_on_MacOS(hass: HomeAssistant) -> None:
    """Test setting up the co2 sensor on MacOS."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOMETERTHPC_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_MAC: "AA:BB:CC:DD:EE:AA",
            CONF_NAME: "test-name",
            CONF_PASSWORD: "test-password",
            CONF_SENSOR_TYPE: "hygrometer_co2",
        },
        unique_id="aabbccddeeaa",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_setup_entry_for_not_ble_device(hass: HomeAssistant) -> None:
    """Test setup entry when not ble device raises ConfigEntryNotReady."""
    await async_setup_component(hass, DOMAIN, {})
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
            CONF_NAME: "test-name",
            CONF_PASSWORD: "test-password",
            CONF_SENSOR_TYPE: "bot",
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    with pytest.raises(
        ConfigEntryNotReady,
        match="Could not find Switchbot bot with address AA:BB:CC:DD:EE:FF",
    ):
        await async_setup_entry(hass, entry)
    assert entry.state == ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_setup_entry_invalid_encryption(hass: HomeAssistant) -> None:
    """Test setup entry when Invalid encryption configuration provided raises ConfigEntryNotReady."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WORELAY_SWITCH_1PM_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "relay_switch_1pm",
            CONF_KEY_ID: "ff",
            CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
        },
        unique_id="aabbccddeeaa",
    )
    entry.add_to_hass(hass)

    with patch("switchbot.SwitchbotDevice.__init__", side_effect=ValueError):
        with pytest.raises(
            ConfigEntryNotReady, match="Invalid encryption configuration provided"
        ):
            await async_setup_entry(hass, entry)
        assert entry.state == ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_setup_entry_for_device_not_ready(hass: HomeAssistant) -> None:
    """Test setup entry when device not ready raises ConfigEntryNotReady."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOHAND_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
            CONF_NAME: "test-name",
            CONF_PASSWORD: "test-password",
            CONF_SENSOR_TYPE: "bot",
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.switchbot.SwitchbotDataUpdateCoordinator.async_wait_ready",
        new=AsyncMock(return_value=False),
    ) as mock_wait_ready:
        with pytest.raises(
            ConfigEntryNotReady, match="AA:BB:CC:DD:EE:FF is not advertising state"
        ):
            await async_setup_entry(hass, entry)

        mock_wait_ready.assert_awaited_once()
        assert entry.state == ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entry_reload(hass: HomeAssistant) -> None:
    """Test realod entry when reselect retry count."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOMETERTHPC_SERVICE_INFO)

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_MAC: "AA:BB:CC:DD:EE:AA",
            CONF_NAME: "test-name",
            CONF_PASSWORD: "test-password",
            CONF_SENSOR_TYPE: "hygrometer_co2",
        },
        unique_id="aabbccddeeaa",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload", new=AsyncMock()
    ) as mock_reload:
        hass.config_entries.async_update_entry(entry, options={"retry_count": 5})
        await hass.async_block_till_done()
        mock_reload.assert_awaited_once_with(entry.entry_id)
