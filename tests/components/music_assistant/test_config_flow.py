"""Define tests for the Music Assistant Integration config flow."""

from copy import deepcopy
from ipaddress import ip_address
from unittest import mock
from unittest.mock import patch

from music_assistant.client.exceptions import CannotConnect, InvalidServerVersion

# pylint: disable=wrong-import-order
from homeassistant.components import zeroconf
from homeassistant.components.music_assistant import config_flow
from homeassistant.components.music_assistant.config_flow import CONF_URL
from homeassistant.components.music_assistant.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DEFAULT_TITLE = "Music Assistant"

VALID_CONFIG = {
    CONF_URL: "http://localhost:8095",
}
VALID_OPTIONS_CONFIG = {
    CONF_URL: "http://localhost:8095",
}

ZEROCONF_DATA = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address("127.0.0.1"),
    ip_addresses=[ip_address("127.0.0.1")],
    hostname="mock_hostname",
    port=None,
    type=mock.ANY,
    name=mock.ANY,
    properties={
        "server_id": "1234",
        "base_url": "http://localhost:8095",
        "server_version": "0.0.0",
        "schema_version": 23,
        "min_supported_schema_version": 23,
        "homeassistant_addon": True,
    },
)


# pylint: disable=dangerous-default-value
async def setup_music_assistant_integration(
    hass: HomeAssistant,
    *,
    config=VALID_CONFIG,
    options=None,
    entry_id="1",
    unique_id="1234",
    source="user",
):
    """Create the Music Assistant integration."""
    if options is None:
        options = {}
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        source=source,
        data=deepcopy(config),
        options=deepcopy(options),
        entry_id=entry_id,
        unique_id=unique_id,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


async def test_flow_user_init_manual_schema(hass: HomeAssistant) -> None:
    """Test the initialization of the form in the first step of the config flow."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    user_input = {CONF_URL: "http://localhost:8095"}
    expected = {
        "data_schema": config_flow.get_manual_schema(user_input=user_input),
        "description_placeholders": None,
        "errors": None,
        "flow_id": mock.ANY,
        "handler": "music_assistant",
        "step_id": "manual",
        "last_step": None,
        "preview": None,
        "type": "form",
    }

    assert result.get("step_id") == expected.get("step_id")
    data_schema = result.get("data_schema")
    assert data_schema is not None
    assert data_schema.schema[CONF_URL] is str


async def test_flow_user_init_zeroconf_schema(hass: HomeAssistant) -> None:
    """Test the initialization of the form in the first step of the config flow."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "zeroconf"}, data=ZEROCONF_DATA
    )
    expected = {
        "data_schema": None,
        "description_placeholders": None,
        "errors": None,
        "flow_id": mock.ANY,
        "handler": "music_assistant",
        "step_id": "discovery_confirm",
        "last_step": None,
        "preview": None,
        "type": "form",
    }
    assert result.get("step_id") == expected.get("step_id")
    data_schema = result.get("data_schema")
    assert data_schema is None


@patch("homeassistant.components.music_assistant.config_flow.get_server_info")
async def test_flow_user_init_connect_issue(m_server_info, hass: HomeAssistant) -> None:
    """Test we advance to the next step when server url is invalid."""
    m_server_info.side_effect = CannotConnect("cannot_connect")

    _result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        _result["flow_id"], user_input={CONF_URL: "bad"}
    )
    assert result["errors"] == {"base": "cannot_connect"}


@patch("homeassistant.components.music_assistant.config_flow.get_server_info")
async def test_flow_user_init_server_version_invalid(
    m_server_info, hass: HomeAssistant
) -> None:
    """Test we advance to the next step when server url is invalid."""
    m_server_info.side_effect = InvalidServerVersion("invalid_server_version")

    _result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        _result["flow_id"], user_input={CONF_URL: "bad"}
    )
    assert result["errors"] == {"base": "invalid_server_version"}


@patch("homeassistant.components.music_assistant.config_flow.MusicAssistantClient")
async def test_flow_discovery_confirm_creates_config_entry(
    m_music_assistant, hass: HomeAssistant
) -> None:
    """Test the config entry is successfully created."""
    config_flow.ConfigFlow.data = VALID_CONFIG
    _result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "zeroconf"}, data=ZEROCONF_DATA
    )
    result = await hass.config_entries.flow.async_configure(
        _result["flow_id"],
    )
    expected = {
        "type": "form",
        "flow_id": mock.ANY,
        "handler": "music_assistant",
        "data_schema": None,
        "errors": None,
        "description_placeholders": {"url": "http://localhost:8095"},
        "last_step": None,
        "preview": None,
        "step_id": "discovery_confirm",
    }
    assert expected == result
