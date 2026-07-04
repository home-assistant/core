"""Test Opentherm Gateway init."""

from unittest.mock import MagicMock

import pyotgw.vars as gw_vars
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


async def test_device_registry_report_numeric_fields(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_pyotgw: MagicMock,
) -> None:
    """Test that numeric device info fields from reports are cast to strings."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    subscribe_call = mock_pyotgw.return_value.subscribe
    assert subscribe_call.call_count == 1
    report_callback = subscribe_call.call_args[0][0]

    await report_callback(
        {
            gw_vars.BOILER: {
                gw_vars.DATA_SLAVE_MEMBERID: 42,
                gw_vars.DATA_SLAVE_PRODUCT_TYPE: 3,
                gw_vars.DATA_SLAVE_PRODUCT_VERSION: 7,
                gw_vars.DATA_SLAVE_OT_VERSION: 2.5,
            },
            gw_vars.THERMOSTAT: {
                gw_vars.DATA_MASTER_MEMBERID: 10,
                gw_vars.DATA_MASTER_PRODUCT_TYPE: 1,
                gw_vars.DATA_MASTER_PRODUCT_VERSION: 4,
                gw_vars.DATA_MASTER_OT_VERSION: 3.0,
            },
        }
    )
    await hass.async_block_till_done()

    boiler_dev = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{MOCK_GATEWAY_ID}-{OpenThermDeviceIdentifier.BOILER}")}
    )
    assert boiler_dev is not None
    assert boiler_dev.manufacturer == "42"
    assert boiler_dev.model_id == "3"
    assert boiler_dev.hw_version == "7"
    assert boiler_dev.sw_version == "2.5"

    thermostat_dev = device_registry.async_get_device(
        identifiers={
            (DOMAIN, f"{MOCK_GATEWAY_ID}-{OpenThermDeviceIdentifier.THERMOSTAT}")
        }
    )
    assert thermostat_dev is not None
    assert thermostat_dev.manufacturer == "10"
    assert thermostat_dev.model_id == "1"
    assert thermostat_dev.hw_version == "4"
    assert thermostat_dev.sw_version == "3.0"
