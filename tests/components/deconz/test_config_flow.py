"""Tests for deCONZ config flow."""
import asyncio
from unittest.mock import Mock, patch

import pydeconz

from homeassistant.components import ssdp
from homeassistant.components.deconz import config_flow

from tests.common import MockConfigEntry


async def test_flow_works(hass, aioclient_mock):
    """Test that config flow works."""
    aioclient_mock.get(
        pydeconz.utils.URL_DISCOVER,
        json=[{"id": "id", "internalipaddress": "1.2.3.4", "internalport": 80}],
        headers={"content-type": "application/json"},
    )
    aioclient_mock.post(
        "http://1.2.3.4:80/api",
        json=[{"success": {"username": "1234567890ABCDEF"}}],
        headers={"content-type": "application/json"},
    )

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "link"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "deCONZ-id"
    assert result["data"] == {
        config_flow.CONF_BRIDGEID: "id",
        config_flow.CONF_HOST: "1.2.3.4",
        config_flow.CONF_PORT: 80,
        config_flow.CONF_API_KEY: "1234567890ABCDEF",
    }


async def test_user_step_bridge_discovery_fails(hass, aioclient_mock):
    """Test config flow works when discovery fails."""
    with patch(
        "homeassistant.components.deconz.config_flow.async_discovery",
        side_effect=asyncio.TimeoutError,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN, context={"source": "user"}
        )

    assert result["type"] == "form"
    assert result["step_id"] == "init"


async def test_user_step_no_discovered_bridges(hass, aioclient_mock):
    """Test config flow discovers no bridges."""
    aioclient_mock.get(
        pydeconz.utils.URL_DISCOVER,
        json=[],
        headers={"content-type": "application/json"},
    )

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "init"


async def test_user_step_one_bridge_discovered(hass, aioclient_mock):
    """Test config flow discovers one bridge."""
    aioclient_mock.get(
        pydeconz.utils.URL_DISCOVER,
        json=[{"id": "id", "internalipaddress": "1.2.3.4", "internalport": 80}],
        headers={"content-type": "application/json"},
    )

    flow = config_flow.DeconzFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user()

    assert result["type"] == "form"
    assert result["step_id"] == "link"
    assert flow.deconz_config[config_flow.CONF_HOST] == "1.2.3.4"


async def test_user_step_two_bridges_discovered(hass, aioclient_mock):
    """Test config flow discovers two bridges."""
    aioclient_mock.get(
        pydeconz.utils.URL_DISCOVER,
        json=[
            {"id": "id1", "internalipaddress": "1.2.3.4", "internalport": 80},
            {"id": "id2", "internalipaddress": "5.6.7.8", "internalport": 80},
        ],
        headers={"content-type": "application/json"},
    )

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["data_schema"]({config_flow.CONF_HOST: "1.2.3.4"})
    assert result["data_schema"]({config_flow.CONF_HOST: "5.6.7.8"})


async def test_user_step_two_bridges_selection(hass, aioclient_mock):
    """Test config flow selection of one of two bridges."""
    flow = config_flow.DeconzFlowHandler()
    flow.hass = hass
    flow.bridges = [
        {
            config_flow.CONF_BRIDGEID: "id1",
            config_flow.CONF_HOST: "1.2.3.4",
            config_flow.CONF_PORT: 80,
        },
        {
            config_flow.CONF_BRIDGEID: "id2",
            config_flow.CONF_HOST: "5.6.7.8",
            config_flow.CONF_PORT: 80,
        },
    ]

    result = await flow.async_step_user(user_input={config_flow.CONF_HOST: "1.2.3.4"})
    assert result["type"] == "form"
    assert result["step_id"] == "link"
    assert flow.deconz_config[config_flow.CONF_HOST] == "1.2.3.4"


async def test_user_step_manual_configuration_no_bridges_discovered(
    hass, aioclient_mock
):
    """Test config flow with manual input."""
    aioclient_mock.get(
        pydeconz.utils.URL_DISCOVER,
        json=[],
        headers={"content-type": "application/json"},
    )

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "init"
    assert not hass.config_entries.flow._progress[result["flow_id"]].bridges

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={config_flow.CONF_HOST: "1.2.3.4", config_flow.CONF_PORT: 80},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "link"


async def test_user_step_manual_configuration_after_timeout(hass):
    """Test config flow with manual input."""
    with patch(
        "homeassistant.components.deconz.config_flow.async_discovery",
        side_effect=asyncio.TimeoutError,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN, context={"source": "user"}
        )

    assert result["type"] == "form"
    assert result["step_id"] == "init"
    assert not hass.config_entries.flow._progress[result["flow_id"]].bridges


async def test_user_step_manual_configuration_after_ResponseError(hass):
    """Test config flow with manual input."""
    with patch(
        "homeassistant.components.deconz.config_flow.async_discovery",
        side_effect=config_flow.ResponseError,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN, context={"source": "user"}
        )

    assert result["type"] == "form"
    assert result["step_id"] == "init"
    assert not hass.config_entries.flow._progress[result["flow_id"]].bridges


async def test_link_no_api_key(hass):
    """Test config flow should abort if no API key was possible to retrieve."""
    flow = config_flow.DeconzFlowHandler()
    flow.hass = hass
    flow.deconz_config = {config_flow.CONF_HOST: "1.2.3.4", config_flow.CONF_PORT: 80}

    with patch(
        "homeassistant.components.deconz.config_flow.async_get_api_key",
        side_effect=pydeconz.errors.ResponseError,
    ):
        result = await flow.async_step_link(user_input={})

    assert result["type"] == "form"
    assert result["step_id"] == "link"
    assert result["errors"] == {"base": "no_key"}


async def test_bridge_ssdp_discovery(hass):
    """Test a bridge being discovered over ssdp."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        data={
            ssdp.ATTR_SSDP_LOCATION: "http://1.2.3.4:80/",
            ssdp.ATTR_UPNP_MANUFACTURER_URL: config_flow.DECONZ_MANUFACTURERURL,
            ssdp.ATTR_UPNP_SERIAL: "id",
            ssdp.ATTR_UPNP_UDN: "uuid:1234",
        },
        context={"source": "ssdp"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "link"


async def test_bridge_ssdp_discovery_not_deconz_bridge(hass):
    """Test a non deconz bridge being discovered over ssdp."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        data={ssdp.ATTR_UPNP_MANUFACTURER_URL: "not deconz bridge"},
        context={"source": "ssdp"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "not_deconz_bridge"


async def test_bridge_discovery_update_existing_entry(hass):
    """Test if a discovered bridge has already been configured."""
    entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        data={
            config_flow.CONF_HOST: "1.2.3.4",
            config_flow.CONF_BRIDGEID: "123ABC",
            config_flow.CONF_UUID: "456DEF",
        },
    )
    entry.add_to_hass(hass)

    gateway = Mock()
    gateway.config_entry = entry
    hass.data[config_flow.DOMAIN] = {"123ABC": gateway}

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        data={
            ssdp.ATTR_SSDP_LOCATION: "http://mock-deconz/",
            ssdp.ATTR_UPNP_MANUFACTURER_URL: config_flow.DECONZ_MANUFACTURERURL,
            ssdp.ATTR_UPNP_SERIAL: "123ABC",
            ssdp.ATTR_UPNP_UDN: "uuid:456DEF",
        },
        context={"source": "ssdp"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "updated_instance"
    assert entry.data[config_flow.CONF_HOST] == "mock-deconz"


async def test_bridge_discovery_dont_update_existing_hassio_entry(hass):
    """Test to ensure the SSDP discovery does not update an Hass.io entry."""
    entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        source="hassio",
        data={
            config_flow.CONF_HOST: "core-deconz",
            config_flow.CONF_BRIDGEID: "123ABC",
            config_flow.CONF_UUID: "456DEF",
        },
    )
    entry.add_to_hass(hass)

    gateway = Mock()
    gateway.config_entry = entry
    hass.data[config_flow.DOMAIN] = {"123ABC": gateway}

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        data={
            ssdp.ATTR_SSDP_LOCATION: "http://mock-deconz/",
            ssdp.ATTR_UPNP_MANUFACTURER_URL: config_flow.DECONZ_MANUFACTURERURL,
            ssdp.ATTR_UPNP_SERIAL: "123ABC",
            ssdp.ATTR_UPNP_UDN: "uuid:456DEF",
        },
        context={"source": "ssdp"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert entry.data[config_flow.CONF_HOST] == "core-deconz"


async def test_create_entry(hass, aioclient_mock):
    """Test that _create_entry work and that bridgeid can be requested."""
    aioclient_mock.get(
        "http://1.2.3.4:80/api/1234567890ABCDEF/config",
        json={"bridgeid": "123ABC", "uuid": "456DEF"},
        headers={"content-type": "application/json"},
    )

    flow = config_flow.DeconzFlowHandler()
    flow.hass = hass
    flow.deconz_config = {
        config_flow.CONF_HOST: "1.2.3.4",
        config_flow.CONF_PORT: 80,
        config_flow.CONF_API_KEY: "1234567890ABCDEF",
    }

    result = await flow._create_entry()

    assert result["type"] == "create_entry"
    assert result["title"] == "deCONZ-123ABC"
    assert result["data"] == {
        config_flow.CONF_BRIDGEID: "123ABC",
        config_flow.CONF_HOST: "1.2.3.4",
        config_flow.CONF_PORT: 80,
        config_flow.CONF_API_KEY: "1234567890ABCDEF",
        config_flow.CONF_UUID: "456DEF",
    }


async def test_create_entry_timeout(hass, aioclient_mock):
    """Test that _create_entry handles a timeout."""
    flow = config_flow.DeconzFlowHandler()
    flow.hass = hass
    flow.deconz_config = {
        config_flow.CONF_HOST: "1.2.3.4",
        config_flow.CONF_PORT: 80,
        config_flow.CONF_API_KEY: "1234567890ABCDEF",
    }

    with patch(
        "homeassistant.components.deconz.config_flow.async_get_gateway_config",
        side_effect=asyncio.TimeoutError,
    ):
        result = await flow._create_entry()

    assert result["type"] == "abort"
    assert result["reason"] == "no_bridges"


async def test_hassio_update_instance(hass):
    """Test we can update an existing config entry."""
    entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        data={
            config_flow.CONF_BRIDGEID: "id",
            config_flow.CONF_HOST: "1.2.3.4",
            config_flow.CONF_PORT: 40850,
            config_flow.CONF_API_KEY: "secret",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        data={
            config_flow.CONF_HOST: "mock-deconz",
            config_flow.CONF_PORT: 8080,
            config_flow.CONF_API_KEY: "updated",
            config_flow.CONF_SERIAL: "id",
        },
        context={"source": "hassio"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "updated_instance"
    assert entry.data[config_flow.CONF_HOST] == "mock-deconz"
    assert entry.data[config_flow.CONF_PORT] == 8080
    assert entry.data[config_flow.CONF_API_KEY] == "updated"


async def test_hassio_dont_update_instance(hass):
    """Test we can update an existing config entry."""
    entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        data={
            config_flow.CONF_BRIDGEID: "id",
            config_flow.CONF_HOST: "1.2.3.4",
            config_flow.CONF_PORT: 8080,
            config_flow.CONF_API_KEY: "secret",
        },
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        data={
            config_flow.CONF_HOST: "1.2.3.4",
            config_flow.CONF_PORT: 8080,
            config_flow.CONF_API_KEY: "secret",
            config_flow.CONF_SERIAL: "id",
        },
        context={"source": "hassio"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_hassio_confirm(hass):
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        data={
            "addon": "Mock Addon",
            config_flow.CONF_HOST: "mock-deconz",
            config_flow.CONF_PORT: 80,
            config_flow.CONF_SERIAL: "id",
            config_flow.CONF_API_KEY: "1234567890ABCDEF",
        },
        context={"source": "hassio"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "hassio_confirm"
    assert result["description_placeholders"] == {"addon": "Mock Addon"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == "create_entry"
    assert result["result"].data == {
        config_flow.CONF_HOST: "mock-deconz",
        config_flow.CONF_PORT: 80,
        config_flow.CONF_BRIDGEID: "id",
        config_flow.CONF_API_KEY: "1234567890ABCDEF",
    }


async def test_option_flow(hass):
    """Test config flow options."""
    entry = MockConfigEntry(domain=config_flow.DOMAIN, data={}, options=None)
    hass.config_entries._entries.append(entry)

    flow = await hass.config_entries.options._async_create_flow(
        entry.entry_id, context={"source": "test"}, data=None
    )

    result = await flow.async_step_init()
    assert result["type"] == "form"
    assert result["step_id"] == "deconz_devices"

    result = await flow.async_step_deconz_devices(
        user_input={
            config_flow.CONF_ALLOW_CLIP_SENSOR: False,
            config_flow.CONF_ALLOW_DECONZ_GROUPS: False,
        }
    )
    assert result["type"] == "create_entry"
    assert result["data"] == {
        config_flow.CONF_ALLOW_CLIP_SENSOR: False,
        config_flow.CONF_ALLOW_DECONZ_GROUPS: False,
    }
