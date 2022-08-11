"""Define tests for the Bravia TV config flow."""
from unittest.mock import patch

from pybravia import BraviaTVConnectionError, BraviaTVNotSupported

from homeassistant import data_entry_flow
from homeassistant.components.braviatv.const import CONF_IGNORED_SOURCES, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PIN

from tests.common import MockConfigEntry

BRAVIA_SYSTEM_INFO = {
    "product": "TV",
    "region": "XEU",
    "language": "pol",
    "model": "TV-Model",
    "serial": "serial_number",
    "macAddr": "AA:BB:CC:DD:EE:FF",
    "name": "BRAVIA",
    "generation": "5.2.0",
    "area": "POL",
    "cid": "very_unique_string",
}

BRAVIA_SOURCES = [
    {"title": "HDMI 1", "uri": "extInput:hdmi?port=1"},
    {"title": "HDMI 2", "uri": "extInput:hdmi?port=2"},
    {"title": "HDMI 3/ARC", "uri": "extInput:hdmi?port=3"},
    {"title": "HDMI 4", "uri": "extInput:hdmi?port=4"},
    {"title": "AV/Component", "uri": "extInput:component?port=1"},
]


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER


async def test_user_invalid_host(hass):
    """Test that errors are shown when the host is invalid."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: "invalid/host"}
    )

    assert result["errors"] == {CONF_HOST: "invalid_host"}


async def test_authorize_cannot_connect(hass):
    """Test that errors are shown when cannot connect to host at the authorize step."""
    with patch(
        "pybravia.BraviaTV.connect",
        side_effect=BraviaTVConnectionError,
    ), patch("pybravia.BraviaTV.pair"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: "bravia-host"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PIN: "1234"}
        )

        assert result["errors"] == {"base": "cannot_connect"}


async def test_authorize_model_unsupported(hass):
    """Test that errors are shown when the TV is not supported at the authorize step."""
    with patch(
        "pybravia.BraviaTV.connect",
        side_effect=BraviaTVNotSupported,
    ), patch("pybravia.BraviaTV.pair"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: "10.10.10.12"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PIN: "1234"}
        )

        assert result["errors"] == {"base": "unsupported_model"}


async def test_authorize_no_ip_control(hass):
    """Test that errors are shown when IP Control is disabled on the TV."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: "bravia-host"}
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "no_ip_control"


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="very_unique_string",
        data={
            CONF_HOST: "bravia-host",
            CONF_PIN: "1234",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
        },
        title="TV-Model",
    )
    config_entry.add_to_hass(hass)

    with patch("pybravia.BraviaTV.connect"), patch("pybravia.BraviaTV.pair"), patch(
        "pybravia.BraviaTV.set_wol_mode"
    ), patch(
        "pybravia.BraviaTV.get_system_info",
        return_value=BRAVIA_SYSTEM_INFO,
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: "bravia-host"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PIN: "1234"}
        )

        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_create_entry(hass):
    """Test that the user step works."""
    with patch("pybravia.BraviaTV.connect"), patch("pybravia.BraviaTV.pair"), patch(
        "pybravia.BraviaTV.set_wol_mode"
    ), patch(
        "pybravia.BraviaTV.get_system_info",
        return_value=BRAVIA_SYSTEM_INFO,
    ), patch(
        "homeassistant.components.braviatv.async_setup_entry", return_value=True
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: "bravia-host"}
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "authorize"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PIN: "1234"}
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["result"].unique_id == "very_unique_string"
        assert result["title"] == "TV-Model"
        assert result["data"] == {
            CONF_HOST: "bravia-host",
            CONF_PIN: "1234",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
        }


async def test_create_entry_with_ipv6_address(hass):
    """Test that the user step works with device IPv6 address."""
    with patch("pybravia.BraviaTV.connect"), patch("pybravia.BraviaTV.pair"), patch(
        "pybravia.BraviaTV.set_wol_mode"
    ), patch(
        "pybravia.BraviaTV.get_system_info",
        return_value=BRAVIA_SYSTEM_INFO,
    ), patch(
        "homeassistant.components.braviatv.async_setup_entry", return_value=True
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_HOST: "2001:db8::1428:57ab"},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "authorize"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PIN: "1234"}
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["result"].unique_id == "very_unique_string"
        assert result["title"] == "TV-Model"
        assert result["data"] == {
            CONF_HOST: "2001:db8::1428:57ab",
            CONF_PIN: "1234",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
        }


async def test_options_flow(hass):
    """Test config flow options."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="very_unique_string",
        data={
            CONF_HOST: "bravia-host",
            CONF_PIN: "1234",
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
        },
        title="TV-Model",
    )
    config_entry.add_to_hass(hass)

    with patch("pybravia.BraviaTV.connect"), patch(
        "pybravia.BraviaTV.get_power_status",
        return_value="active",
    ), patch(
        "pybravia.BraviaTV.get_external_status",
        return_value=BRAVIA_SOURCES,
    ), patch(
        "pybravia.BraviaTV.send_rest_req",
        return_value={},
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_IGNORED_SOURCES: ["HDMI 1", "HDMI 2"]}
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert config_entry.options == {CONF_IGNORED_SOURCES: ["HDMI 1", "HDMI 2"]}
