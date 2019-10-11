"""Test Mikrotik hub."""
from asynctest import patch
import librouteros
import pytest

from homeassistant import config_entries
from homeassistant.components import mikrotik
from homeassistant.exceptions import ConfigEntryNotReady

from . import DHCP_DATA, MOCK_DATA, WIRELESS_DATA

CONFIG_ENTRY = config_entries.ConfigEntry(
    version=1,
    domain=mikrotik.DOMAIN,
    title="Mikrotik",
    data=MOCK_DATA,
    source="test",
    connection_class=config_entries.CONN_CLASS_LOCAL_POLL,
    system_options={},
    options={},
    entry_id=1,
)


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

    config_entry = CONFIG_ENTRY
    if "force_dhcp" in kwargs:
        config_entry.options["force_dhcp"] = True

    with patch("librouteros.connect"), patch.object(
        mikrotik.hub.MikrotikData, "command", new=mock_command
    ):
        await mikrotik.async_setup_entry(hass, config_entry)
        await hass.async_block_till_done()
        return hass.data[mikrotik.DOMAIN][CONFIG_ENTRY.data[mikrotik.CONF_HOST]]


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
    assert hub.config_entry.system_options == config_entries.SystemOptions(
        disable_new_entities=False
    )
    assert hub.api.available is True
    assert hub.signal_update == "mikrotik-update-0.0.0.0"
    assert forward_entry_setup.mock_calls[0][1] == (hub.config_entry, "device_tracker")


async def test_hub_setup_failed(hass):
    """Failed setup of Mikrotik hub."""

    # error when connection fails
    with patch(
        "librouteros.connect", side_effect=librouteros.exceptions.ConnectionError
    ):
        with pytest.raises(ConfigEntryNotReady):
            await mikrotik.async_setup_entry(hass, CONFIG_ENTRY)

    # error when username or password is invalid
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setup"
    ) as forward_entry_setup, patch(
        "librouteros.connect",
        side_effect=librouteros.exceptions.TrapError("invalid user name or password"),
    ):
        result = await mikrotik.async_setup_entry(hass, CONFIG_ENTRY)

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

    # test that the devices are constructed from wireless data

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
    assert "00:00:00:00:00:02" not in hub.api.devices


async def test_force_dhcp(hass):
    """Test updating hub devices with forced dhcp method."""

    # test that the devices are constructed from dhcp data

    hub = await setup_mikrotik_entry(hass, force_dhcp=True)

    assert hub.api.support_wireless is True
    assert hub.api.devices["00:00:00:00:00:01"]._params == DHCP_DATA[0]
    assert hub.api.devices["00:00:00:00:00:01"]._wireless_params == WIRELESS_DATA[0]
    assert hub.api.devices["00:00:00:00:00:02"]._params == DHCP_DATA[1]
    assert hub.api.devices["00:00:00:00:00:02"]._wireless_params is None
