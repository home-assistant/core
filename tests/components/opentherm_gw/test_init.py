"""Test Opentherm Gateway init."""
from unittest.mock import patch

from pyotgw.vars import OTGW, OTGW_ABOUT
import pytest

from homeassistant import setup
from homeassistant.components.opentherm_gw.const import DOMAIN
from homeassistant.const import CONF_DEVICE, CONF_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

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
async def test_device_registry_insert(hass: HomeAssistant) -> None:
    """Test that the device registry is initialized correctly."""
    MOCK_CONFIG_ENTRY.add_to_hass(hass)

    with patch(
        "homeassistant.components.opentherm_gw.OpenThermGatewayDevice.cleanup",
        return_value=None,
    ), patch("pyotgw.OpenThermGateway.connect", return_value=MINIMAL_STATUS):
        await setup.async_setup_component(hass, DOMAIN, {})

    await hass.async_block_till_done()

    device_registry = dr.async_get(hass)

    gw_dev = device_registry.async_get_device(identifiers={(DOMAIN, MOCK_GATEWAY_ID)})
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
        identifiers={(DOMAIN, MOCK_GATEWAY_ID)},
        name="Mock Gateway",
        manufacturer="Schelte Bron",
        model="OpenTherm Gateway",
        sw_version=VERSION_OLD,
    )

    with patch(
        "homeassistant.components.opentherm_gw.OpenThermGatewayDevice.cleanup",
        return_value=None,
    ), patch("pyotgw.OpenThermGateway.connect", return_value=MINIMAL_STATUS_UPD):
        await setup.async_setup_component(hass, DOMAIN, {})

    await hass.async_block_till_done()
    gw_dev = device_registry.async_get_device(identifiers={(DOMAIN, MOCK_GATEWAY_ID)})
    assert gw_dev.sw_version == VERSION_NEW
