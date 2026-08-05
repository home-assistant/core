"""Test the Tesla Wall Connector config flow."""

from tesla_wall_connector.exceptions import WallConnectorConnectionError

from homeassistant.components.tesla_wall_connector.const import (
    DOMAIN,
    WALLCONNECTOR_DEVICE_MANUFACTURER,
    WALLCONNECTOR_DEVICE_MODEL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import (
    create_wall_connector_entry,
    get_lifetime_mock,
    get_vitals_mock,
    get_wifi_status_mock,
)


async def test_init_success(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test setup and that we get the device info, including firmware version."""

    entry = await create_wall_connector_entry(
        hass,
        vitals_data=get_vitals_mock(),
        lifetime_data=get_lifetime_mock(),
        wifi_status_data=get_wifi_status_mock(),
    )

    assert entry.state is ConfigEntryState.LOADED
    device = device_registry.async_get_device(identifiers={(DOMAIN, "abc123")})
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
