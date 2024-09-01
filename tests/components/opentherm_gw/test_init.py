"""Test Opentherm Gateway init."""

from unittest.mock import AsyncMock, MagicMock, patch

from pyotgw.vars import OTGW, OTGW_ABOUT
import pytest

from homeassistant import setup
from homeassistant.components.opentherm_gw.const import (
    DOMAIN,
    OpenThermDeviceIdentifier,
)
from homeassistant.const import CONF_DEVICE, CONF_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

VERSION_OLD = "4.2.5"
VERSION_NEW = "4.2.8.1"
MINIMAL_STATUS = {OTGW: {OTGW_ABOUT: f"OpenTherm Gateway {VERSION_OLD}"}}
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


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_device_registry_insert(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test that the device registry is initialized correctly."""
    MOCK_CONFIG_ENTRY.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.opentherm_gw.OpenThermGatewayHub.cleanup",
            return_value=None,
        ),
        patch("pyotgw.OpenThermGateway.connect", return_value=MINIMAL_STATUS),
    ):
        await setup.async_setup_component(hass, DOMAIN, {})

    await hass.async_block_till_done()

    gw_dev = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{MOCK_GATEWAY_ID}-{OpenThermDeviceIdentifier.GATEWAY}")}
    )
    assert gw_dev.sw_version == VERSION_OLD


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_device_registry_update(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
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
        sw_version=VERSION_OLD,
    )

    with (
        patch(
            "homeassistant.components.opentherm_gw.OpenThermGatewayHub.cleanup",
            return_value=None,
        ),
        patch("pyotgw.OpenThermGateway.connect", return_value=MINIMAL_STATUS_UPD),
    ):
        await setup.async_setup_component(hass, DOMAIN, {})

    await hass.async_block_till_done()
    gw_dev = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{MOCK_GATEWAY_ID}-{OpenThermDeviceIdentifier.GATEWAY}")}
    )
    assert gw_dev is not None
    assert gw_dev.sw_version == VERSION_NEW


# Device migration test can be removed in 2025.4.0
async def test_device_migration(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
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
        sw_version=VERSION_OLD,
    )

    with (
        patch(
            "homeassistant.components.opentherm_gw.OpenThermGateway",
            return_value=MagicMock(
                connect=AsyncMock(return_value=MINIMAL_STATUS_UPD),
                set_control_setpoint=AsyncMock(),
                set_max_relative_mod=AsyncMock(),
                disconnect=AsyncMock(),
            ),
        ),
    ):
        await setup.async_setup_component(hass, DOMAIN, {})

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
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that the climate entity unique_id gets migrated correctly."""
    MOCK_CONFIG_ENTRY.add_to_hass(hass)
    entry = entity_registry.async_get_or_create(
        domain="climate",
        platform="opentherm_gw",
        unique_id=MOCK_CONFIG_ENTRY.data[CONF_ID],
    )

    with (
        patch(
            "homeassistant.components.opentherm_gw.OpenThermGateway",
            return_value=MagicMock(
                connect=AsyncMock(return_value=MINIMAL_STATUS_UPD),
                set_control_setpoint=AsyncMock(),
                set_max_relative_mod=AsyncMock(),
                disconnect=AsyncMock(),
            ),
        ),
    ):
        await setup.async_setup_component(hass, DOMAIN, {})

    await hass.async_block_till_done()

    assert (
        entity_registry.async_get(entry.entity_id).unique_id
        == f"{MOCK_CONFIG_ENTRY.data[CONF_ID]}-{OpenThermDeviceIdentifier.THERMOSTAT}-thermostat_entity"
    )
