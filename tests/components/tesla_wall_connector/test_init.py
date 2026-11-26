"""Test the Tesla Wall Connector config flow."""

import asyncio
from functools import partial
from unittest.mock import MagicMock, patch

from pytest_homeassistant.common import MockConfigEntry
from tesla_wall_connector import WallConnector
from tesla_wall_connector.exceptions import WallConnectorConnectionError

from homeassistant.components.tesla_wall_connector.const import (
    DOMAIN,
    WALLCONNECTOR_DEVICE_MANUFACTURER,
    WALLCONNECTOR_DEVICE_MODEL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import (
    create_wall_connector_entry,
    get_default_version_data,
    get_lifetime_mock,
    get_vitals_mock,
    get_wifi_status_mock,
)


async def test_init_success(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test that setup fetches device info without overlapping requests."""
    request_active = False

    async def fetch[T](data: T) -> T:
        nonlocal request_active
        assert not request_active, "Wall Connector requests must not overlap"
        request_active = True
        try:
            await asyncio.sleep(0)
            return data
        finally:
            request_active = False

    client = MagicMock(spec=WallConnector)
    client.async_get_version.return_value = get_default_version_data()
    client.async_get_vitals.side_effect = partial(fetch, get_vitals_mock())
    client.async_get_lifetime.side_effect = partial(fetch, get_lifetime_mock())
    client.async_get_wifi_status.side_effect = partial(fetch, get_wifi_status_mock())
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.2.3.4"})
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.tesla_wall_connector.WallConnector",
        return_value=client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    client.async_get_vitals.assert_awaited_once()
    client.async_get_lifetime.assert_awaited_once()
    client.async_get_wifi_status.assert_awaited_once()
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "abc123"), entry.entry_id
    )
    assert device
    assert device.manufacturer == WALLCONNECTOR_DEVICE_MANUFACTURER
    assert device.model == WALLCONNECTOR_DEVICE_MODEL
    assert device.model_id == "part_123"
    assert device.serial_number == "abc123"
    assert device.sw_version == "1.2.3"


async def test_init_while_offline(hass: HomeAssistant) -> None:
    """Test init with the wall connector offline."""
    entry = await create_wall_connector_entry(
        hass, side_effect=WallConnectorConnectionError
    )

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_load_unload(hass: HomeAssistant) -> None:
    """Config entry can be unloaded."""

    entry = await create_wall_connector_entry(
        hass,
        vitals_data=get_vitals_mock(),
        lifetime_data=get_lifetime_mock(),
        wifi_status_data=get_wifi_status_mock(),
    )
    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
