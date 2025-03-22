"""Helper functions for Haus-Bus tests."""

from threading import Thread
from typing import cast
from unittest.mock import Mock, patch

from pyhausbus.de.hausbus.homeassistant.proxy.controller.data.ModuleId import ModuleId
from pyhausbus.de.hausbus.homeassistant.proxy.controller.params.EFirmwareId import (
    EFirmwareId,
)
from pyhausbus.HomeServer import HomeServer
from pyhausbus.ObjectId import ObjectId

from homeassistant.components.hausbus.const import DOMAIN as HAUSBUS_DOMAIN
from homeassistant.components.hausbus.entity import HausbusEntity
from homeassistant.components.hausbus.gateway import HausbusGateway
from homeassistant.components.hausbus.light import HausbusLight
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from tests.common import MockConfigEntry

BRIDGEID = "01234E56789A"
HOST = "1.2.3.4"

HAUSBUS_CONFIG = {
    "bridgeid": BRIDGEID,
    "ipaddress": HOST,
    "mac": "00:11:22:33:44:55",
    "modelid": "hausbus",
    "name": "hausbus mock gateway",
    "sw_version": "2.05.69",
    "uuid": "1234",
}


async def create_configuration(hass: HomeAssistant, flow: FlowResult) -> FlowResult:
    """Fill configuration form."""
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    await hass.async_block_till_done()
    return result


async def setup_hausbus_integration(hass: HomeAssistant, *, entry_id="1"):
    """Create a mock config entry."""
    config_entry = MockConfigEntry(
        domain=HAUSBUS_DOMAIN,
        entry_id=entry_id,
    )

    config_entry.add_to_hass(hass)

    hass.data.setdefault(HAUSBUS_DOMAIN, {})

    # Create a mock HomeServer
    mock_home_server = Mock(Spec=HomeServer)

    # Patch the HomeServer constructor to return the mock_home_server
    with patch(
        "homeassistant.components.hausbus.gateway.HomeServer",
        return_value=mock_home_server,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


async def create_gateway(hass: HomeAssistant):
    """Create a hausbus gateway."""
    config_entry = await setup_hausbus_integration(hass)

    # return gateway that was added ti the config entry
    # return hass.data[HAUSBUS_DOMAIN][config_entry.entry_id]
    return config_entry.runtime_data.gateway


async def add_channel_from_thread(
    hass: HomeAssistant, channel: HausbusEntity, gateway: HausbusGateway
):
    """Add a channel to the gateway via a different thread."""

    # channels are added from a bus message thread
    thread = Thread(target=gateway.add_channel, args=[channel])
    thread.start()
    # channel entity creation is added to hass loop, wait until this is finished
    while thread.is_alive():
        await hass.async_block_till_done()
    thread.join()

    # adding entity is done asynchronously on hass loop, wait until this is finished
    await hass.async_block_till_done()


async def create_light_channel(hass: HomeAssistant, instance):
    """Add a light channel to the gateway via a different thread."""
    gateway = await create_gateway(hass)

    # get mock config entry with id "1"
    config_entry = hass.config_entries.async_get_entry("1")

    # setup light domain
    await hass.config_entries.async_forward_entry_setups(config_entry, [Platform.LIGHT])

    # Add a new device to hold the dimmer channel
    device_id = "1"
    module = ModuleId("module", 0, 1, 0, EFirmwareId.ESP32)
    gateway.add_device(device_id, module)
    await add_channel_from_thread(hass, instance, gateway)

    return gateway, cast(
        HausbusLight, gateway.get_channel(ObjectId(instance.getObjectId()))
    )
