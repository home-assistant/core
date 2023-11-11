"""Helper functions for Haus-Bus tests."""

from threading import Thread
from unittest.mock import Mock, patch

from pyhausbus.HomeServer import HomeServer

from homeassistant.components.hausbus.channel import HausbusChannel
from homeassistant.components.hausbus.const import DOMAIN as HAUSBUS_DOMAIN
from homeassistant.components.hausbus.gateway import HausbusGateway
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
    config_entry.add_to_manager(hass.config_entries)

    hass.data.setdefault(HAUSBUS_DOMAIN, {})

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


async def create_gateway(hass: HomeAssistant):
    """Create a hausbus gateway."""
    config_entry = await setup_hausbus_integration(hass)

    # Create a mock HomeServer
    mock_home_server = Mock(Spec=HomeServer)

    # Patch the HomeServer constructor to return the mock_home_server
    with patch(
        "homeassistant.components.hausbus.gateway.HomeServer",
        return_value=mock_home_server,
    ):
        # Create a HausbusGateway instance
        gateway = HausbusGateway(hass, config_entry)

    # add gateway to hass
    hass.data[HAUSBUS_DOMAIN][config_entry.entry_id] = gateway

    return gateway, mock_home_server


async def add_channel_from_thread(
    hass: HomeAssistant, channel: HausbusChannel, gateway: HausbusGateway
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
