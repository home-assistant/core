"""Tests for deCONZ config flow."""

import asyncio
from unittest.mock import patch

import pydeconz

from homeassistant.components.deconz.config_flow import (
    CONF_MANUAL_INPUT,
    CONF_SERIAL,
    DECONZ_MANUFACTURERURL,
)
from homeassistant.components.deconz.const import (
    CONF_ALLOW_CLIP_SENSOR,
    CONF_ALLOW_DECONZ_GROUPS,
    CONF_ALLOW_NEW_DEVICES,
    CONF_MASTER_GATEWAY,
    DOMAIN,
)
from homeassistant.components.ssdp import (
    ATTR_SSDP_LOCATION,
    ATTR_UPNP_MANUFACTURER_URL,
    ATTR_UPNP_SERIAL,
)
from homeassistant.config_entries import SOURCE_HASSIO, SOURCE_SSDP, SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONTENT_TYPE_JSON
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from .test_gateway import API_KEY, BRIDGEID, setup_deconz_integration

BAD_BRIDGEID = "0000000000000000"


async def test_flow_discovered_bridges(hass, aioclient_mock):
    """Test that config flow works for discovered bridges."""
    aioclient_mock.get(
        pydeconz.utils.URL_DISCOVER,
        json=[
            {"id": BRIDGEID, "internalipaddress": "1.2.3.4", "internalport": 80},
            {"id": "1234E567890A", "internalipaddress": "5.6.7.8", "internalport": 80},
        ],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "1.2.3.4"}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "link"

    aioclient_mock.post(
        "http://1.2.3.4:80/api",
        json=[{"success": {"username": API_KEY}}],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == BRIDGEID
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_PORT: 80,
        CONF_API_KEY: API_KEY,
    }


async def test_flow_manual_configuration_decision(hass, aioclient_mock):
    """Test that config flow for one discovered bridge works."""
    aioclient_mock.get(
        pydeconz.utils.URL_DISCOVER,
        json=[{"id": BRIDGEID, "internalipaddress": "1.2.3.4", "internalport": 80}],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: CONF_MANUAL_INPUT}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "manual_input"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "1.2.3.4", CONF_PORT: 80},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "link"

    aioclient_mock.post(
        "http://1.2.3.4:80/api",
        json=[{"success": {"username": API_KEY}}],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://1.2.3.4:80/api/{API_KEY}/config",
        json={"bridgeid": BRIDGEID},
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == BRIDGEID
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_PORT: 80,
        CONF_API_KEY: API_KEY,
    }


async def test_flow_manual_configuration(hass, aioclient_mock):
    """Test that config flow works with manual configuration after no discovered bridges."""
    aioclient_mock.get(
        pydeconz.utils.URL_DISCOVER,
        json=[],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "manual_input"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "1.2.3.4", CONF_PORT: 80},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "link"

    aioclient_mock.post(
        "http://1.2.3.4:80/api",
        json=[{"success": {"username": API_KEY}}],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://1.2.3.4:80/api/{API_KEY}/config",
        json={"bridgeid": BRIDGEID},
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == BRIDGEID
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_PORT: 80,
        CONF_API_KEY: API_KEY,
    }


async def test_manual_configuration_after_discovery_timeout(hass, aioclient_mock):
    """Test failed discovery fallbacks to manual configuration."""
    aioclient_mock.get(pydeconz.utils.URL_DISCOVER, exc=asyncio.TimeoutError)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "manual_input"
    assert not hass.config_entries.flow._progress[result["flow_id"]].bridges


async def test_manual_configuration_after_discovery_ResponseError(hass, aioclient_mock):
    """Test failed discovery fallbacks to manual configuration."""
    aioclient_mock.get(pydeconz.utils.URL_DISCOVER, exc=pydeconz.errors.ResponseError)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "manual_input"
    assert not hass.config_entries.flow._progress[result["flow_id"]].bridges


async def test_manual_configuration_update_configuration(hass, aioclient_mock):
    """Test that manual configuration can update existing config entry."""
    config_entry = await setup_deconz_integration(hass)

    aioclient_mock.get(
        pydeconz.utils.URL_DISCOVER,
        json=[],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "manual_input"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "2.3.4.5", CONF_PORT: 80},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "link"

    aioclient_mock.post(
        "http://2.3.4.5:80/api",
        json=[{"success": {"username": API_KEY}}],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://2.3.4.5:80/api/{API_KEY}/config",
        json={"bridgeid": BRIDGEID},
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_HOST] == "2.3.4.5"


async def test_manual_configuration_dont_update_configuration(hass, aioclient_mock):
    """Test that _create_entry work and that bridgeid can be requested."""
    await setup_deconz_integration(hass)

    aioclient_mock.get(
        pydeconz.utils.URL_DISCOVER,
        json=[],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "manual_input"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "1.2.3.4", CONF_PORT: 80},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "link"

    aioclient_mock.post(
        "http://1.2.3.4:80/api",
        json=[{"success": {"username": API_KEY}}],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://1.2.3.4:80/api/{API_KEY}/config",
        json={"bridgeid": BRIDGEID},
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_manual_configuration_timeout_get_bridge(hass, aioclient_mock):
    """Test that _create_entry handles a timeout."""
    aioclient_mock.get(
        pydeconz.utils.URL_DISCOVER,
        json=[],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "manual_input"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "1.2.3.4", CONF_PORT: 80},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "link"

    aioclient_mock.post(
        "http://1.2.3.4:80/api",
        json=[{"success": {"username": API_KEY}}],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://1.2.3.4:80/api/{API_KEY}/config", exc=asyncio.TimeoutError
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "no_bridges"


async def test_link_get_api_key_ResponseError(hass, aioclient_mock):
    """Test config flow should abort if no API key was possible to retrieve."""
    aioclient_mock.get(
        pydeconz.utils.URL_DISCOVER,
        json=[{"id": BRIDGEID, "internalipaddress": "1.2.3.4", "internalport": 80}],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "1.2.3.4"}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "link"

    aioclient_mock.post("http://1.2.3.4:80/api", exc=pydeconz.errors.ResponseError)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "link"
    assert result["errors"] == {"base": "no_key"}


async def test_flow_ssdp_discovery(hass, aioclient_mock):
    """Test that config flow for one discovered bridge works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data={
            ATTR_SSDP_LOCATION: "http://1.2.3.4:80/",
            ATTR_UPNP_MANUFACTURER_URL: DECONZ_MANUFACTURERURL,
            ATTR_UPNP_SERIAL: BRIDGEID,
        },
        context={"source": SOURCE_SSDP},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "link"

    aioclient_mock.post(
        "http://1.2.3.4:80/api",
        json=[{"success": {"username": API_KEY}}],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == BRIDGEID
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_PORT: 80,
        CONF_API_KEY: API_KEY,
    }


async def test_ssdp_discovery_update_configuration(hass):
    """Test if a discovered bridge is configured but updates with new attributes."""
    config_entry = await setup_deconz_integration(hass)

    with patch(
        "homeassistant.components.deconz.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data={
                ATTR_SSDP_LOCATION: "http://2.3.4.5:80/",
                ATTR_UPNP_MANUFACTURER_URL: DECONZ_MANUFACTURERURL,
                ATTR_UPNP_SERIAL: BRIDGEID,
            },
            context={"source": SOURCE_SSDP},
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_HOST] == "2.3.4.5"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_ssdp_discovery_dont_update_configuration(hass):
    """Test if a discovered bridge has already been configured."""
    config_entry = await setup_deconz_integration(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data={
            ATTR_SSDP_LOCATION: "http://1.2.3.4:80/",
            ATTR_UPNP_MANUFACTURER_URL: DECONZ_MANUFACTURERURL,
            ATTR_UPNP_SERIAL: BRIDGEID,
        },
        context={"source": SOURCE_SSDP},
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_HOST] == "1.2.3.4"


async def test_ssdp_discovery_dont_update_existing_hassio_configuration(hass):
    """Test to ensure the SSDP discovery does not update an Hass.io entry."""
    config_entry = await setup_deconz_integration(hass, source=SOURCE_HASSIO)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data={
            ATTR_SSDP_LOCATION: "http://1.2.3.4:80/",
            ATTR_UPNP_MANUFACTURER_URL: DECONZ_MANUFACTURERURL,
            ATTR_UPNP_SERIAL: BRIDGEID,
        },
        context={"source": SOURCE_SSDP},
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_HOST] == "1.2.3.4"


async def test_flow_hassio_discovery(hass):
    """Test hassio discovery flow works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data={
            "addon": "Mock Addon",
            CONF_HOST: "mock-deconz",
            CONF_PORT: 80,
            CONF_SERIAL: BRIDGEID,
            CONF_API_KEY: API_KEY,
        },
        context={"source": SOURCE_HASSIO},
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "hassio_confirm"
    assert result["description_placeholders"] == {"addon": "Mock Addon"}

    with patch(
        "homeassistant.components.deconz.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.deconz.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["result"].data == {
        CONF_HOST: "mock-deconz",
        CONF_PORT: 80,
        CONF_API_KEY: API_KEY,
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_hassio_discovery_update_configuration(hass):
    """Test we can update an existing config entry."""
    config_entry = await setup_deconz_integration(hass)

    with patch(
        "homeassistant.components.deconz.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data={
                CONF_HOST: "2.3.4.5",
                CONF_PORT: 8080,
                CONF_API_KEY: "updated",
                CONF_SERIAL: BRIDGEID,
            },
            context={"source": SOURCE_HASSIO},
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_HOST] == "2.3.4.5"
    assert config_entry.data[CONF_PORT] == 8080
    assert config_entry.data[CONF_API_KEY] == "updated"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_hassio_discovery_dont_update_configuration(hass):
    """Test we can update an existing config entry."""
    await setup_deconz_integration(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data={
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 80,
            CONF_API_KEY: API_KEY,
            CONF_SERIAL: BRIDGEID,
        },
        context={"source": SOURCE_HASSIO},
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_option_flow(hass):
    """Test config flow options."""
    config_entry = await setup_deconz_integration(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "deconz_devices"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_ALLOW_CLIP_SENSOR: False,
            CONF_ALLOW_DECONZ_GROUPS: False,
            CONF_ALLOW_NEW_DEVICES: False,
        },
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        CONF_ALLOW_CLIP_SENSOR: False,
        CONF_ALLOW_DECONZ_GROUPS: False,
        CONF_ALLOW_NEW_DEVICES: False,
        CONF_MASTER_GATEWAY: True,
    }
