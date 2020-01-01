"""Tests for Philips Hue config flow."""
import asyncio
from unittest.mock import Mock, patch

import aiohue
import pytest
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import ssdp
from homeassistant.components.hue import config_flow, const

from tests.common import MockConfigEntry, mock_coro


async def test_flow_works(hass):
    """Test config flow ."""
    mock_bridge = Mock()
    mock_bridge.host = "1.2.3.4"
    mock_bridge.username = None
    mock_bridge.config.name = "Mock Bridge"
    mock_bridge.id = "aabbccddeeff"

    async def mock_create_user(username):
        mock_bridge.username = username

    mock_bridge.create_user = mock_create_user
    mock_bridge.initialize.return_value = mock_coro()

    flow = config_flow.HueFlowHandler()
    flow.hass = hass
    flow.context = {}

    with patch(
        "homeassistant.components.hue.config_flow.discover_nupnp",
        return_value=mock_coro([mock_bridge]),
    ):
        result = await flow.async_step_init()

    assert result["type"] == "form"
    assert result["step_id"] == "link"

    assert flow.context["unique_id"] == "aabbccddeeff"

    result = await flow.async_step_link(user_input={})

    assert result["type"] == "create_entry"
    assert result["title"] == "Mock Bridge"
    assert result["data"] == {
        "host": "1.2.3.4",
        "username": "home-assistant#test-home",
    }

    assert len(mock_bridge.initialize.mock_calls) == 1


async def test_flow_no_discovered_bridges(hass, aioclient_mock):
    """Test config flow discovers no bridges."""
    aioclient_mock.get(const.API_NUPNP, json=[])
    flow = config_flow.HueFlowHandler()
    flow.hass = hass

    result = await flow.async_step_init()
    assert result["type"] == "abort"


async def test_flow_all_discovered_bridges_exist(hass, aioclient_mock):
    """Test config flow discovers only already configured bridges."""
    aioclient_mock.get(
        const.API_NUPNP, json=[{"internalipaddress": "1.2.3.4", "id": "bla"}]
    )
    MockConfigEntry(
        domain="hue", unique_id="bla", data={"host": "1.2.3.4"}
    ).add_to_hass(hass)
    flow = config_flow.HueFlowHandler()
    flow.hass = hass
    flow.context = {}

    result = await flow.async_step_init()
    assert result["type"] == "abort"


async def test_flow_one_bridge_discovered(hass, aioclient_mock):
    """Test config flow discovers one bridge."""
    aioclient_mock.get(
        const.API_NUPNP, json=[{"internalipaddress": "1.2.3.4", "id": "bla"}]
    )
    flow = config_flow.HueFlowHandler()
    flow.hass = hass
    flow.context = {}

    result = await flow.async_step_init()
    assert result["type"] == "form"
    assert result["step_id"] == "link"


async def test_flow_two_bridges_discovered(hass, aioclient_mock):
    """Test config flow discovers two bridges."""
    # Add ignored config entry. Should still show up as option.
    MockConfigEntry(
        domain="hue", source=config_entries.SOURCE_IGNORE, unique_id="bla"
    ).add_to_hass(hass)

    aioclient_mock.get(
        const.API_NUPNP,
        json=[
            {"internalipaddress": "1.2.3.4", "id": "bla"},
            {"internalipaddress": "5.6.7.8", "id": "beer"},
        ],
    )
    flow = config_flow.HueFlowHandler()
    flow.hass = hass

    result = await flow.async_step_init()
    assert result["type"] == "form"
    assert result["step_id"] == "init"

    with pytest.raises(vol.Invalid):
        assert result["data_schema"]({"id": "not-discovered"})

    result["data_schema"]({"id": "bla"})
    result["data_schema"]({"id": "beer"})


async def test_flow_two_bridges_discovered_one_new(hass, aioclient_mock):
    """Test config flow discovers two bridges."""
    aioclient_mock.get(
        const.API_NUPNP,
        json=[
            {"internalipaddress": "1.2.3.4", "id": "bla"},
            {"internalipaddress": "5.6.7.8", "id": "beer"},
        ],
    )
    MockConfigEntry(
        domain="hue", unique_id="bla", data={"host": "1.2.3.4"}
    ).add_to_hass(hass)
    flow = config_flow.HueFlowHandler()
    flow.hass = hass
    flow.context = {}

    result = await flow.async_step_init()
    assert result["type"] == "form"
    assert result["step_id"] == "link"
    assert flow.bridge.host == "5.6.7.8"


async def test_flow_timeout_discovery(hass):
    """Test config flow ."""
    flow = config_flow.HueFlowHandler()
    flow.hass = hass

    with patch(
        "homeassistant.components.hue.config_flow.discover_nupnp",
        side_effect=asyncio.TimeoutError,
    ):
        result = await flow.async_step_init()

    assert result["type"] == "abort"


async def test_flow_link_timeout(hass):
    """Test config flow ."""
    flow = config_flow.HueFlowHandler()
    flow.hass = hass
    flow.bridge = Mock()

    with patch("aiohue.Bridge.create_user", side_effect=asyncio.TimeoutError):
        result = await flow.async_step_link({})

    assert result["type"] == "form"
    assert result["step_id"] == "link"
    assert result["errors"] == {"base": "linking"}


async def test_flow_link_button_not_pressed(hass):
    """Test config flow ."""
    flow = config_flow.HueFlowHandler()
    flow.hass = hass
    flow.bridge = Mock(
        username=None, create_user=Mock(side_effect=aiohue.LinkButtonNotPressed)
    )

    result = await flow.async_step_link({})

    assert result["type"] == "form"
    assert result["step_id"] == "link"
    assert result["errors"] == {"base": "register_failed"}


async def test_flow_link_unknown_host(hass):
    """Test config flow ."""
    flow = config_flow.HueFlowHandler()
    flow.hass = hass
    flow.bridge = Mock()

    with patch("aiohue.Bridge.create_user", side_effect=aiohue.RequestError):
        result = await flow.async_step_link({})

    assert result["type"] == "form"
    assert result["step_id"] == "link"
    assert result["errors"] == {"base": "linking"}


async def test_bridge_ssdp(hass):
    """Test a bridge being discovered."""
    flow = config_flow.HueFlowHandler()
    flow.hass = hass
    flow.context = {}

    result = await flow.async_step_ssdp(
        {
            ssdp.ATTR_SSDP_LOCATION: "http://0.0.0.0/",
            ssdp.ATTR_UPNP_MANUFACTURER_URL: config_flow.HUE_MANUFACTURERURL,
            ssdp.ATTR_UPNP_SERIAL: "1234",
        }
    )

    assert result["type"] == "form"
    assert result["step_id"] == "link"


async def test_bridge_ssdp_discover_other_bridge(hass):
    """Test that discovery ignores other bridges."""
    flow = config_flow.HueFlowHandler()
    flow.hass = hass

    result = await flow.async_step_ssdp(
        {ssdp.ATTR_UPNP_MANUFACTURER_URL: "http://www.notphilips.com"}
    )

    assert result["type"] == "abort"


async def test_bridge_ssdp_emulated_hue(hass):
    """Test if discovery info is from an emulated hue instance."""
    flow = config_flow.HueFlowHandler()
    flow.hass = hass
    flow.context = {}

    result = await flow.async_step_ssdp(
        {
            ssdp.ATTR_SSDP_LOCATION: "http://0.0.0.0/",
            ssdp.ATTR_UPNP_FRIENDLY_NAME: "HASS Bridge",
            ssdp.ATTR_UPNP_MANUFACTURER_URL: config_flow.HUE_MANUFACTURERURL,
            ssdp.ATTR_UPNP_SERIAL: "1234",
        }
    )

    assert result["type"] == "abort"
    assert result["reason"] == "not_hue_bridge"


async def test_bridge_ssdp_espalexa(hass):
    """Test if discovery info is from an Espalexa based device."""
    flow = config_flow.HueFlowHandler()
    flow.hass = hass
    flow.context = {}

    result = await flow.async_step_ssdp(
        {
            ssdp.ATTR_SSDP_LOCATION: "http://0.0.0.0/",
            ssdp.ATTR_UPNP_FRIENDLY_NAME: "Espalexa (0.0.0.0)",
            ssdp.ATTR_UPNP_MANUFACTURER_URL: config_flow.HUE_MANUFACTURERURL,
            ssdp.ATTR_UPNP_SERIAL: "1234",
        }
    )

    assert result["type"] == "abort"
    assert result["reason"] == "not_hue_bridge"


async def test_bridge_ssdp_already_configured(hass):
    """Test if a discovered bridge has already been configured."""
    MockConfigEntry(
        domain="hue", unique_id="1234", data={"host": "0.0.0.0"}
    ).add_to_hass(hass)

    flow = config_flow.HueFlowHandler()
    flow.hass = hass
    flow.context = {}

    with pytest.raises(data_entry_flow.AbortFlow):
        await flow.async_step_ssdp(
            {
                ssdp.ATTR_SSDP_LOCATION: "http://0.0.0.0/",
                ssdp.ATTR_UPNP_MANUFACTURER_URL: config_flow.HUE_MANUFACTURERURL,
                ssdp.ATTR_UPNP_SERIAL: "1234",
            }
        )


async def test_import_with_no_config(hass):
    """Test importing a host without an existing config file."""
    flow = config_flow.HueFlowHandler()
    flow.hass = hass
    flow.context = {}

    result = await flow.async_step_import({"host": "0.0.0.0"})

    assert result["type"] == "form"
    assert result["step_id"] == "link"


async def test_creating_entry_removes_entries_for_same_host_or_bridge(hass):
    """Test that we clean up entries for same host and bridge.

    An IP can only hold a single bridge and a single bridge can only be
    accessible via a single IP. So when we create a new entry, we'll remove
    all existing entries that either have same IP or same bridge_id.
    """
    orig_entry = MockConfigEntry(
        domain="hue", data={"host": "0.0.0.0", "username": "aaaa"}, unique_id="id-1234",
    )
    orig_entry.add_to_hass(hass)

    MockConfigEntry(
        domain="hue", data={"host": "1.2.3.4", "username": "bbbb"}, unique_id="id-5678",
    ).add_to_hass(hass)

    assert len(hass.config_entries.async_entries("hue")) == 2

    bridge = Mock()
    bridge.username = "username-abc"
    bridge.config.name = "Mock Bridge"
    bridge.host = "0.0.0.0"
    bridge.id = "id-1234"

    with patch(
        "aiohue.Bridge", return_value=bridge,
    ):
        result = await hass.config_entries.flow.async_init(
            "hue", data={"host": "2.2.2.2"}, context={"source": "import"}
        )

    assert result["type"] == "form"
    assert result["step_id"] == "link"

    with patch(
        "homeassistant.components.hue.config_flow.authenticate_bridge",
        return_value=mock_coro(),
    ), patch(
        "homeassistant.components.hue.async_setup_entry",
        side_effect=lambda _, _2: mock_coro(True),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == "create_entry"
    assert result["title"] == "Mock Bridge"
    assert result["data"] == {
        "host": "0.0.0.0",
        "username": "username-abc",
    }
    entries = hass.config_entries.async_entries("hue")
    assert len(entries) == 2
    new_entry = entries[-1]
    assert orig_entry.entry_id != new_entry.entry_id
    assert new_entry.unique_id == "id-1234"


async def test_bridge_homekit(hass):
    """Test a bridge being discovered via HomeKit."""
    flow = config_flow.HueFlowHandler()
    flow.hass = hass
    flow.context = {}

    result = await flow.async_step_homekit(
        {
            "host": "0.0.0.0",
            "serial": "1234",
            "manufacturerURL": config_flow.HUE_MANUFACTURERURL,
            "properties": {"id": "aa:bb:cc:dd:ee:ff"},
        }
    )

    assert result["type"] == "form"
    assert result["step_id"] == "link"


async def test_bridge_homekit_already_configured(hass):
    """Test if a HomeKit discovered bridge has already been configured."""
    MockConfigEntry(
        domain="hue", unique_id="aabbccddeeff", data={"host": "0.0.0.0"}
    ).add_to_hass(hass)

    flow = config_flow.HueFlowHandler()
    flow.hass = hass
    flow.context = {}

    with pytest.raises(data_entry_flow.AbortFlow):
        await flow.async_step_homekit(
            {"host": "0.0.0.0", "properties": {"id": "aa:bb:cc:dd:ee:ff"}}
        )
