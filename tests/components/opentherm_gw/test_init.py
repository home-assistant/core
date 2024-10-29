"""Test Opentherm Gateway init."""

from unittest.mock import MagicMock

from pyotgw.vars import OTGW, OTGW_ABOUT

from homeassistant import setup
from homeassistant.components.opentherm_gw.const import (
    DOMAIN,
    OpenThermDeviceIdentifier,
)
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

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


# Device migration test can be removed in 2025.4.0
async def test_device_migration(
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
            (DOMAIN, MOCK_GATEWAY_ID),
        },
        name="Mock Gateway",
        manufacturer="Schelte Bron",
        model="OpenTherm Gateway",
        sw_version=VERSION_TEST,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
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
    mock_config_entry: MockConfigEntry,
    mock_pyotgw: MagicMock,
) -> None:
    """Test that the climate entity unique_id gets migrated correctly."""
    mock_config_entry.add_to_hass(hass)
    entry = entity_registry.async_get_or_create(
        domain="climate",
        platform="opentherm_gw",
        unique_id=mock_config_entry.data[CONF_ID],
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    updated_entry = entity_registry.async_get(entry.entity_id)
    assert updated_entry is not None
    assert (
        updated_entry.unique_id
        == f"{mock_config_entry.data[CONF_ID]}-{OpenThermDeviceIdentifier.THERMOSTAT}-thermostat_entity"
    )


# Deprecation test, can be removed in 2025.4.0
async def test_configuration_yaml_deprecation(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    mock_pyotgw: MagicMock,
) -> None:
    """Test that existing configuration in configuration.yaml creates an issue."""

    await setup.async_setup_component(
        hass, DOMAIN, {DOMAIN: {"legacy_gateway": {"device": "/dev/null"}}}
    )

    await hass.async_block_till_done()
    assert (
        issue_registry.async_get_issue(
            DOMAIN, "deprecated_import_from_configuration_yaml"
        )
        is not None
    )
