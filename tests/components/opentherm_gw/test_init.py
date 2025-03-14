"""Test Opentherm Gateway init."""

from unittest.mock import MagicMock

from pyotgw.vars import OTGW, OTGW_ABOUT

from homeassistant.components.opentherm_gw.const import (
    DOMAIN,
    OpenThermDeviceIdentifier,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import MOCK_GATEWAY_ID, VERSION_TEST

from tests.common import MockConfigEntry

VERSION_NEW = "4.2.8.1"
MINIMAL_STATUS_UPD = {OTGW: {OTGW_ABOUT: f"OpenTherm Gateway {VERSION_NEW}"}}


async def test_device_registry_insert(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_pyotgw: MagicMock,
) -> None:
    """Test that the device registry is initialized correctly."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    gw_dev = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{MOCK_GATEWAY_ID}-{OpenThermDeviceIdentifier.GATEWAY}")}
    )
    assert gw_dev is not None
    assert gw_dev.sw_version == VERSION_TEST


async def test_device_registry_update(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_pyotgw: MagicMock,
) -> None:
    """Test that the device registry is updated correctly."""
    mock_config_entry.add_to_hass(hass)

    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={
            (DOMAIN, f"{MOCK_GATEWAY_ID}-{OpenThermDeviceIdentifier.GATEWAY}")
        },
        name="Mock Gateway",
        manufacturer="Schelte Bron",
        model="OpenTherm Gateway",
        sw_version=VERSION_TEST,
    )

    mock_pyotgw.return_value.connect.return_value = MINIMAL_STATUS_UPD

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    gw_dev = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{MOCK_GATEWAY_ID}-{OpenThermDeviceIdentifier.GATEWAY}")}
    )
    assert gw_dev is not None
    assert gw_dev.sw_version == VERSION_NEW
