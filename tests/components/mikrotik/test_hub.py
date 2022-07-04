"""Test Mikrotik hub."""
from unittest.mock import patch

from homeassistant.components import mikrotik

from . import ARP_DATA, DHCP_DATA, MOCK_DATA, MOCK_OPTIONS, WIRELESS_DATA

from tests.common import MockConfigEntry


async def setup_mikrotik_entry(hass, **kwargs):
    """Set up Mikrotik integration successfully."""
    support_wireless = kwargs.get("support_wireless", True)
    dhcp_data = kwargs.get("dhcp_data", DHCP_DATA)
    wireless_data = kwargs.get("wireless_data", WIRELESS_DATA)

    def mock_command(self, cmd, params=None):
        if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.IS_WIRELESS]:
            return support_wireless
        if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.DHCP]:
            return dhcp_data
        if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.WIRELESS]:
            return wireless_data
        if cmd == mikrotik.const.MIKROTIK_SERVICES[mikrotik.const.ARP]:
            return ARP_DATA
        return {}

    config_entry = MockConfigEntry(
        domain=mikrotik.DOMAIN, data=MOCK_DATA, options=MOCK_OPTIONS
    )
    config_entry.add_to_hass(hass)

    if "force_dhcp" in kwargs:
        config_entry.options = {**config_entry.options, "force_dhcp": True}

    if "arp_ping" in kwargs:
        config_entry.options = {**config_entry.options, "arp_ping": True}

    with patch("librouteros.connect"), patch.object(
        mikrotik.hub.MikrotikData, "command", new=mock_command
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        return hass.data[mikrotik.DOMAIN][config_entry.entry_id]
