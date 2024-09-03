"""Test Opentherm Gateway init."""

from unittest.mock import MagicMock

from pyotgw.vars import OTGW, OTGW_ABOUT

from homeassistant.components.opentherm_gw.const import (
    DOMAIN,
    OpenThermDeviceIdentifier,
)
from homeassistant.const import CONF_DEVICE, CONF_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import VERSION_TEST

from tests.common import MockConfigEntry

VERSION_NEW = "4.2.8.1"
MINIMAL_STATUS_UPD = {OTGW: {OTGW_ABOUT: f"OpenTherm Gateway {VERSION_NEW}"}}
MOCK_GATEWAY_ID = "mock_gateway"
MOCK_CONFIG_ENTRY = MockConfigEntry(
    domain=DOMAIN,
    title="Mock Gateway",
    data={
        CONF_NAME: "Mock Gateway",
        CONF_DEVICE: "/dev/null",
        CONF_ID: MOCK_GATEWAY_ID,
    },
    options={},
)


async def test_device_registry_insert(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_pyotgw: MagicMock,
) -> None:
    """Test that the device registry is initialized correctly."""
    MOCK_CONFIG_ENTRY.add_to_hass(hass)

    await hass.config_entries.async_setup(MOCK_CONFIG_ENTRY.entry_id)
    await hass.async_block_till_done()

    gw_dev = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{MOCK_GATEWAY_ID}-{OpenThermDeviceIdentifier.GATEWAY}")}
    )
    assert gw_dev is not None
    assert gw_dev.sw_version == VERSION_TEST


async def test_device_registry_update(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_pyotgw: MagicMock,
) -> None:
    """Test that the device registry is updated correctly."""
    MOCK_CONFIG_ENTRY.add_to_hass(hass)

    device_registry.async_get_or_create(
        config_entry_id=MOCK_CONFIG_ENTRY.entry_id,
        identifiers={
            (DOMAIN, f"{MOCK_GATEWAY_ID}-{OpenThermDeviceIdentifier.GATEWAY}")
        },
        name="Mock Gateway",
        manufacturer="Schelte Bron",
        model="OpenTherm Gateway",
        sw_version=VERSION_TEST,
    )

    mock_pyotgw.return_value.connect.return_value = MINIMAL_STATUS_UPD

    await hass.config_entries.async_setup(MOCK_CONFIG_ENTRY.entry_id)
    await hass.async_block_till_done()

    gw_dev = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{MOCK_GATEWAY_ID}-{OpenThermDeviceIdentifier.GATEWAY}")}
    )
    assert gw_dev is not None
    assert gw_dev.sw_version == VERSION_NEW


# Device migration test can be removed in 2025.4.0
async def test_device_migration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_pyotgw: MagicMock,
) -> None:
    """Test that the device registry is updated correctly."""
    MOCK_CONFIG_ENTRY.add_to_hass(hass)

    device_registry.async_get_or_create(
        config_entry_id=MOCK_CONFIG_ENTRY.entry_id,
        identifiers={
            (DOMAIN, MOCK_GATEWAY_ID),
        },
        name="Mock Gateway",
        manufacturer="Schelte Bron",
        model="OpenTherm Gateway",
        sw_version=VERSION_TEST,
    )

    await hass.config_entries.async_setup(MOCK_CONFIG_ENTRY.entry_id)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, MOCK_GATEWAY_ID)})
        is None
    )

    gw_dev = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{MOCK_GATEWAY_ID}-{OpenThermDeviceIdentifier.GATEWAY}")}
    )
    assert gw_dev is not None

    assert (
        device_registry.async_get_device(
            identifiers={
                (DOMAIN, f"{MOCK_GATEWAY_ID}-{OpenThermDeviceIdentifier.BOILER}")
            }
        )
        is not None
    )

    assert (
        device_registry.async_get_device(
            identifiers={
                (DOMAIN, f"{MOCK_GATEWAY_ID}-{OpenThermDeviceIdentifier.THERMOSTAT}")
            }
        )
        is not None
    )


# Entity migration test can be removed in 2025.4.0
async def test_climate_entity_migration(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_pyotgw: MagicMock,
) -> None:
    """Test that the climate entity unique_id gets migrated correctly."""
    MOCK_CONFIG_ENTRY.add_to_hass(hass)
    entry = entity_registry.async_get_or_create(
        domain="climate",
        platform="opentherm_gw",
        unique_id=MOCK_CONFIG_ENTRY.data[CONF_ID],
    )

    await hass.config_entries.async_setup(MOCK_CONFIG_ENTRY.entry_id)
    await hass.async_block_till_done()

    updated_entry = entity_registry.async_get(entry.entity_id)
    assert updated_entry is not None
    assert (
        updated_entry.unique_id
        == f"{MOCK_CONFIG_ENTRY.data[CONF_ID]}-{OpenThermDeviceIdentifier.THERMOSTAT}-thermostat_entity"
    )
