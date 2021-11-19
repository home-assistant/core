"""Test the Balboa Spa Client integration."""
import asyncio
from unittest.mock import patch

from homeassistant.components.balboa.const import DOMAIN as BALBOA_DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

BALBOA_DEFAULT_PORT = 4257
TEST_HOST = "balboatest.localdomain"


async def init_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Mock integration setup."""
    config_entry = MockConfigEntry(
        domain=BALBOA_DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.balboa.BalboaSpaWifi",
        new=BalboaMock,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


async def init_integration_mocked(hass: HomeAssistant) -> MockConfigEntry:
    """Mock integration setup."""
    config_entry = MockConfigEntry(
        domain=BALBOA_DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.balboa.BalboaSpaWifi.connect",
        new=BalboaMock.connect,
    ), patch(
        "homeassistant.components.balboa.BalboaSpaWifi.listen_until_configured",
        new=BalboaMock.listen_until_configured,
    ), patch(
        "homeassistant.components.balboa.BalboaSpaWifi.listen",
        new=BalboaMock.listen,
    ), patch(
        "homeassistant.components.balboa.BalboaSpaWifi.check_connection_status",
        new=BalboaMock.check_connection_status,
    ), patch(
        "homeassistant.components.balboa.BalboaSpaWifi.send_panel_req",
        new=BalboaMock.send_panel_req,
    ), patch(
        "homeassistant.components.balboa.BalboaSpaWifi.send_mod_ident_req",
        new=BalboaMock.send_mod_ident_req,
    ), patch(
        "homeassistant.components.balboa.BalboaSpaWifi.spa_configured",
        new=BalboaMock.spa_configured,
    ), patch(
        "homeassistant.components.balboa.BalboaSpaWifi.get_model_name",
        new=BalboaMock.get_model_name,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


class BalboaMock:
    """Mock pybalboa library."""

    def __init__(self, hostname, port=BALBOA_DEFAULT_PORT):
        """Mock init."""
        self.host = hostname
        self.port = port
        self.connected = False
        self.new_data_cb = None
        self.lastupd = 0
        self.connected = False
        self.fake_action = False

    async def connect(self):
        """Connect to the spa."""
        self.connected = True
        return True

    async def broken_connect(self):
        """Connect to the spa."""
        self.connected = False
        return False

    async def disconnect(self):
        """Stop talking to the spa."""
        self.connected = False

    async def send_panel_req(self, arg_ba, arg_bb):
        """Send a panel request, 2 bytes of data."""
        self.fake_action = False
        return

    async def send_mod_ident_req(self):
        """Ask for the module identification."""
        self.fake_action = False
        return

    @staticmethod
    def get_macaddr():
        """Return the macaddr of the spa wifi."""
        return "ef:ef:ef:c0:ff:ee"

    def get_model_name(self):
        """Return the model name."""
        self.fake_action = False
        return "FakeSpa"

    @staticmethod
    def get_ssid():
        """Return the software version."""
        return "V0.0"

    @staticmethod
    async def set_time(new_time, timescale=None):
        """Set time on spa to new_time with optional timescale."""
        return

    async def listen(self):
        """Listen to the spa babble forever."""
        while True:
            if not self.connected:
                # sleep and hope the checker fixes us
                await asyncio.sleep(5)
                continue

            # fake it
            await asyncio.sleep(5)

    async def check_connection_status(self):
        """Set this up to periodically check the spa connection and fix."""
        self.fake_action = False
        while True:
            # fake it
            await asyncio.sleep(15)

    async def spa_configured(self):
        """Check if the spa has been configured."""
        self.fake_action = False
        return

    async def int_new_data_cb(self):
        """Call false internal data callback."""

        if self.new_data_cb is None:
            return
        await self.new_data_cb()  # pylint: disable=not-callable

    async def listen_until_configured(self, maxiter=20):
        """Listen to the spa babble until we are configured."""
        if not self.connected:
            return False
        return True
