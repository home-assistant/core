"""Test Mikrotik hub."""
import librouteros

from homeassistant import config_entries
from homeassistant.components import mikrotik

from . import ARP_DATA, DHCP_DATA, MOCK_DATA, MOCK_OPTIONS, WIRELESS_DATA

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def setup_mikrotik_entry(hass, **kwargs):
    """Set up Mikrotik intergation successfully."""
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


async def test_hub_setup_successful(hass):
    """Successful setup of Mikrotik hub."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setup",
        return_value=True,
    ) as forward_entry_setup:
        hub = await setup_mikrotik_entry(hass)

    assert hub.config_entry.data == {
        mikrotik.CONF_NAME: "Mikrotik",
        mikrotik.CONF_HOST: "0.0.0.0",
        mikrotik.CONF_USERNAME: "user",
        mikrotik.CONF_PASSWORD: "pass",
        mikrotik.CONF_PORT: 8278,
        mikrotik.CONF_VERIFY_SSL: False,
    }
    assert hub.config_entry.options == {
        mikrotik.hub.CONF_FORCE_DHCP: False,
        mikrotik.CONF_ARP_PING: False,
        mikrotik.CONF_DETECTION_TIME: 300,
    }

    assert hub.api.available is True
    assert hub.signal_update == "mikrotik-update-0.0.0.0"
    assert forward_entry_setup.mock_calls[0][1] == (hub.config_entry, "device_tracker")


async def test_hub_setup_failed(hass):
    """Failed setup of Mikrotik hub."""

    config_entry = MockConfigEntry(domain=mikrotik.DOMAIN, data=MOCK_DATA)
    config_entry.add_to_hass(hass)
    # error when connection fails
    with patch(
        "librouteros.connect", side_effect=librouteros.exceptions.ConnectionClosed
    ):

        await hass.config_entries.async_setup(config_entry.entry_id)

        assert config_entry.state == config_entries.ENTRY_STATE_SETUP_RETRY

    # error when username or password is invalid
    config_entry = MockConfigEntry(domain=mikrotik.DOMAIN, data=MOCK_DATA)
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setup"
    ) as forward_entry_setup, patch(
        "librouteros.connect",
        side_effect=librouteros.exceptions.TrapError("invalid user name or password"),
    ):

        result = await hass.config_entries.async_setup(config_entry.entry_id)

        assert result is False
        assert len(forward_entry_setup.mock_calls) == 0


async def test_update_failed(hass):
    """Test failing to connect during update."""

    hub = await setup_mikrotik_entry(hass)

    with patch.object(
        mikrotik.hub.MikrotikData, "command", side_effect=mikrotik.errors.CannotConnect
    ):
        await hub.async_update()

    assert hub.api.available is False


async def test_hub_not_support_wireless(hass):
    """Test updating hub devices when hub doesn't support wireless interfaces."""

    # test that the devices are constructed from dhcp data

    hub = await setup_mikrotik_entry(hass, support_wireless=False)

    assert hub.api.devices["00:00:00:00:00:01"]._params == DHCP_DATA[0]
    assert hub.api.devices["00:00:00:00:00:01"]._wireless_params is None
    assert hub.api.devices["00:00:00:00:00:02"]._params == DHCP_DATA[1]
    assert hub.api.devices["00:00:00:00:00:02"]._wireless_params is None


async def test_hub_support_wireless(hass):
    """Test updating hub devices when hub support wireless interfaces."""

    # test that the device list is from wireless data list

    hub = await setup_mikrotik_entry(hass)

    assert hub.api.support_wireless is True
    assert hub.api.devices["00:00:00:00:00:01"]._params == DHCP_DATA[0]
    assert hub.api.devices["00:00:00:00:00:01"]._wireless_params == WIRELESS_DATA[0]

    # devices not in wireless list will not be added
    assert "00:00:00:00:00:02" not in hub.api.devices


async def test_force_dhcp(hass):
    """Test updating hub devices with forced dhcp method."""

    # test that the devices are constructed from dhcp data

    hub = await setup_mikrotik_entry(hass, force_dhcp=True)

    assert hub.api.support_wireless is True
    assert hub.api.devices["00:00:00:00:00:01"]._params == DHCP_DATA[0]
    assert hub.api.devices["00:00:00:00:00:01"]._wireless_params == WIRELESS_DATA[0]

    # devices not in wireless list are added from dhcp
    assert hub.api.devices["00:00:00:00:00:02"]._params == DHCP_DATA[1]
    assert hub.api.devices["00:00:00:00:00:02"]._wireless_params is None


async def test_arp_ping(hass):
    """Test arp ping devices to confirm they are connected."""

    # test device show as home if arp ping returns value
    with patch.object(mikrotik.hub.MikrotikData, "do_arp_ping", return_value=True):
        hub = await setup_mikrotik_entry(hass, arp_ping=True, force_dhcp=True)

        assert hub.api.devices["00:00:00:00:00:01"].last_seen is not None
        assert hub.api.devices["00:00:00:00:00:02"].last_seen is not None

    # test device show as away if arp ping times out
    with patch.object(mikrotik.hub.MikrotikData, "do_arp_ping", return_value=False):
        hub = await setup_mikrotik_entry(hass, arp_ping=True, force_dhcp=True)

        assert hub.api.devices["00:00:00:00:00:01"].last_seen is not None
        # this device is not wireless so it will show as away
        assert hub.api.devices["00:00:00:00:00:02"].last_seen is None
