"""Tests for the Balboa Spa Client integration."""
import asyncio

BALBOA_DEFAULT_PORT = 4257


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

    @staticmethod
    async def send_panel_req(arg_ba, arg_bb):
        """Send a panel request, 2 bytes of data."""
        return

    @staticmethod
    async def send_mod_ident_req():
        """Ask for the module identification."""
        return

    @staticmethod
    def get_macaddr():
        """Return the macaddr of the spa wifi."""
        return "ef:ef:ef:c0:ff:ee"

    @staticmethod
    def get_model_name():
        """Return the model name."""
        return "Fake"

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

    @staticmethod
    async def check_connection_status():
        """Set this up to periodically check the spa connection and fix."""
        while True:
            # fake it
            await asyncio.sleep(15)

    @staticmethod
    async def spa_configured():
        """Check if the spa has been configured."""
        return
