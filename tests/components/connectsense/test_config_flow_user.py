from unittest.mock import patch
import pytest
from homeassistant.components.connectsense import config_flow
from homeassistant.const import CONF_HOST
from tests.common import MockConfigEntry

DOMAIN = "connectsense"
pytestmark = pytest.mark.usefixtures("mock_zeroconf")

async def test_user_flow_hostname(hass):
    host = "rebooter-pro.local"
    serial = "1000001"

    with patch.object(config_flow, "_probe_serial_over_https", return_value=serial):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        assert result["type"] == "form"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: host}
        )

    assert result2["type"] == "create_entry"
    assert result2["data"] == {CONF_HOST: host}
    assert serial in result2["title"]

async def test_user_flow_ip_prefers_mdns(hass):
    ip = "22.22.22.49"
    mdns = "rebooter-pro-2.local"
    serial = "1000002"

    with patch.object(config_flow, "_mdns_hostname_for_ip", return_value=mdns), \
         patch.object(config_flow, "_probe_serial_over_https", return_value=serial):

        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: ip}
        )

    assert result2["type"] == "create_entry"
    assert result2["data"][CONF_HOST] == mdns
    assert serial in result2["title"]

async def test_user_flow_dedupe_when_exists(hass):
    host = "rebooter-pro.local"
    serial = "1000001"
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: host}, unique_id=serial)
    entry.add_to_hass(hass)

    with patch.object(config_flow, "_probe_serial_over_https", return_value=serial):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: host}
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_user_flow_cannot_connect(hass):
    ip = "1.2.3.4"
    with patch.object(config_flow, "_probe_serial_over_https", side_effect=Exception), \
         patch.object(config_flow, "_mdns_hostname_for_ip", return_value=None):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: ip}
        )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_zeroconf_confirm(hass):
    serial = "1000003"
    with patch.object(config_flow, "_probe_serial_over_https", return_value=serial):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "zeroconf"},
            data={
                "hostname": "rebooter-pro.local.",
                "properties": {"api": "local", "protocol": "https"},
                "name": "rebooter-pro",
            },
        )
        assert result["type"] == "form"
        assert result["step_id"] == "zeroconf_confirm"

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})

    assert result2["type"] == "create_entry"
    assert serial in result2["title"]
