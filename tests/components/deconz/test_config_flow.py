"""Tests for deCONZ config flow."""

import logging
from unittest.mock import patch

import pydeconz
import pytest

from homeassistant.components import ssdp
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
    DOMAIN as DECONZ_DOMAIN,
    HASSIO_CONFIGURATION_URL,
)
from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.components.ssdp import ATTR_UPNP_MANUFACTURER_URL, ATTR_UPNP_SERIAL
from homeassistant.config_entries import SOURCE_HASSIO, SOURCE_SSDP, SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import API_KEY, BRIDGE_ID

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

BAD_BRIDGEID = "0000000000000000"


async def test_flow_discovered_bridges(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that config flow works for discovered bridges."""
    logging.getLogger("homeassistant.components.deconz").setLevel(logging.DEBUG)
    aioclient_mock.get(
        pydeconz.utils.URL_DISCOVER,
        json=[
            {"id": BRIDGE_ID, "internalipaddress": "1.2.3.4", "internalport": 80},
            {"id": "1234E567890A", "internalipaddress": "5.6.7.8", "internalport": 80},
        ],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DECONZ_DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "1.2.3.4"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "link"

    aioclient_mock.post(
        "http://1.2.3.4:80/api",
        json=[{"success": {"username": API_KEY}}],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == BRIDGE_ID
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_PORT: 80,
        CONF_API_KEY: API_KEY,
    }


async def test_flow_manual_configuration_decision(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that config flow for one discovered bridge works."""
    aioclient_mock.get(
        pydeconz.utils.URL_DISCOVER,
        json=[{"id": BRIDGE_ID, "internalipaddress": "1.2.3.4", "internalport": 80}],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DECONZ_DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: CONF_MANUAL_INPUT}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual_input"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "1.2.3.4", CONF_PORT: 80},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "link"

    aioclient_mock.post(
        "http://1.2.3.4:80/api",
        json=[{"success": {"username": API_KEY}}],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://1.2.3.4:80/api/{API_KEY}/config",
        json={"bridgeid": BRIDGE_ID},
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == BRIDGE_ID
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_PORT: 80,
        CONF_API_KEY: API_KEY,
    }


async def test_flow_manual_configuration(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that config flow works with manual configuration after no discovered bridges."""
    logging.getLogger("homeassistant.components.deconz").setLevel(logging.DEBUG)
    aioclient_mock.get(
        pydeconz.utils.URL_DISCOVER,
        json=[],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DECONZ_DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual_input"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "1.2.3.4", CONF_PORT: 80},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "link"

    aioclient_mock.post(
        "http://1.2.3.4:80/api",
        json=[{"success": {"username": API_KEY}}],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://1.2.3.4:80/api/{API_KEY}/config",
        json={"bridgeid": BRIDGE_ID},
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == BRIDGE_ID
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_PORT: 80,
        CONF_API_KEY: API_KEY,
    }


async def test_manual_configuration_after_discovery_timeout(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test failed discovery fallbacks to manual configuration."""
    aioclient_mock.get(pydeconz.utils.URL_DISCOVER, exc=TimeoutError)

    result = await hass.config_entries.flow.async_init(
        DECONZ_DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual_input"
    assert not hass.config_entries.flow._progress[result["flow_id"]].bridges


async def test_manual_configuration_after_discovery_ResponseError(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test failed discovery fallbacks to manual configuration."""
    aioclient_mock.get(pydeconz.utils.URL_DISCOVER, exc=pydeconz.errors.ResponseError)

    result = await hass.config_entries.flow.async_init(
        DECONZ_DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual_input"
    assert not hass.config_entries.flow._progress[result["flow_id"]].bridges


async def test_manual_configuration_update_configuration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Test that manual configuration can update existing config entry."""
    aioclient_mock.get(
        pydeconz.utils.URL_DISCOVER,
        json=[],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DECONZ_DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual_input"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "2.3.4.5", CONF_PORT: 80},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "link"

    aioclient_mock.post(
        "http://2.3.4.5:80/api",
        json=[{"success": {"username": API_KEY}}],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://2.3.4.5:80/api/{API_KEY}/config",
        json={"bridgeid": BRIDGE_ID},
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry_setup.data[CONF_HOST] == "2.3.4.5"


@pytest.mark.usefixtures("config_entry_setup")
async def test_manual_configuration_dont_update_configuration(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that _create_entry work and that bridgeid can be requested."""
    aioclient_mock.get(
        pydeconz.utils.URL_DISCOVER,
        json=[],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DECONZ_DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual_input"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "1.2.3.4", CONF_PORT: 80},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "link"

    aioclient_mock.post(
        "http://1.2.3.4:80/api",
        json=[{"success": {"username": API_KEY}}],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://1.2.3.4:80/api/{API_KEY}/config",
        json={"bridgeid": BRIDGE_ID},
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_manual_configuration_timeout_get_bridge(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that _create_entry handles a timeout."""
    aioclient_mock.get(
        pydeconz.utils.URL_DISCOVER,
        json=[],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DECONZ_DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual_input"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "1.2.3.4", CONF_PORT: 80},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "link"

    aioclient_mock.post(
        "http://1.2.3.4:80/api",
        json=[{"success": {"username": API_KEY}}],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(f"http://1.2.3.4:80/api/{API_KEY}/config", exc=TimeoutError)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_bridges"


@pytest.mark.parametrize(
    ("raised_error", "error_string"),
    [
        (pydeconz.errors.LinkButtonNotPressed, "linking_not_possible"),
        (TimeoutError, "no_key"),
        (pydeconz.errors.ResponseError, "no_key"),
        (pydeconz.errors.RequestError, "no_key"),
    ],
)
async def test_link_step_fails(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    raised_error: Exception,
    error_string: str,
) -> None:
    """Test config flow should abort if no API key was possible to retrieve."""
    aioclient_mock.get(
        pydeconz.utils.URL_DISCOVER,
        json=[{"id": BRIDGE_ID, "internalipaddress": "1.2.3.4", "internalport": 80}],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_init(
        DECONZ_DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "1.2.3.4"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "link"

    aioclient_mock.post("http://1.2.3.4:80/api", exc=raised_error)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "link"
    assert result["errors"] == {"base": error_string}


async def test_reauth_flow_update_configuration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Verify reauth flow can update gateway API key."""
    result = await config_entry_setup.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "link"

    new_api_key = "new_key"

    aioclient_mock.post(
        "http://1.2.3.4:80/api",
        json=[{"success": {"username": new_api_key}}],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"http://1.2.3.4:80/api/{new_api_key}/config",
        json={"bridgeid": BRIDGE_ID},
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry_setup.data[CONF_API_KEY] == new_api_key


async def test_flow_ssdp_discovery(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that config flow for one discovered bridge works."""
    result = await hass.config_entries.flow.async_init(
        DECONZ_DOMAIN,
        data=ssdp.SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="http://1.2.3.4:80/",
            upnp={
                ATTR_UPNP_MANUFACTURER_URL: DECONZ_MANUFACTURERURL,
                ATTR_UPNP_SERIAL: BRIDGE_ID,
            },
        ),
        context={"source": SOURCE_SSDP},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "link"

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0].get("context", {}).get("configuration_url") == "http://1.2.3.4:80"

    aioclient_mock.post(
        "http://1.2.3.4:80/api",
        json=[{"success": {"username": API_KEY}}],
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == BRIDGE_ID
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_PORT: 80,
        CONF_API_KEY: API_KEY,
    }


async def test_ssdp_discovery_update_configuration(
    hass: HomeAssistant, config_entry_setup: MockConfigEntry
) -> None:
    """Test if a discovered bridge is configured but updates with new attributes."""
    with patch(
        "homeassistant.components.deconz.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DECONZ_DOMAIN,
            data=ssdp.SsdpServiceInfo(
                ssdp_usn="mock_usn",
                ssdp_st="mock_st",
                ssdp_location="http://2.3.4.5:80/",
                upnp={
                    ATTR_UPNP_MANUFACTURER_URL: DECONZ_MANUFACTURERURL,
                    ATTR_UPNP_SERIAL: BRIDGE_ID,
                },
            ),
            context={"source": SOURCE_SSDP},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry_setup.data[CONF_HOST] == "2.3.4.5"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_ssdp_discovery_dont_update_configuration(
    hass: HomeAssistant, config_entry_setup: MockConfigEntry
) -> None:
    """Test if a discovered bridge has already been configured."""

    result = await hass.config_entries.flow.async_init(
        DECONZ_DOMAIN,
        data=ssdp.SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="http://1.2.3.4:80/",
            upnp={
                ATTR_UPNP_MANUFACTURER_URL: DECONZ_MANUFACTURERURL,
                ATTR_UPNP_SERIAL: BRIDGE_ID,
            },
        ),
        context={"source": SOURCE_SSDP},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry_setup.data[CONF_HOST] == "1.2.3.4"


@pytest.mark.parametrize("config_entry_source", [SOURCE_HASSIO])
async def test_ssdp_discovery_dont_update_existing_hassio_configuration(
    hass: HomeAssistant, config_entry_setup: MockConfigEntry
) -> None:
    """Test to ensure the SSDP discovery does not update an Hass.io entry."""
    result = await hass.config_entries.flow.async_init(
        DECONZ_DOMAIN,
        data=ssdp.SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="http://1.2.3.4:80/",
            upnp={
                ATTR_UPNP_MANUFACTURER_URL: DECONZ_MANUFACTURERURL,
                ATTR_UPNP_SERIAL: BRIDGE_ID,
            },
        ),
        context={"source": SOURCE_SSDP},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry_setup.data[CONF_HOST] == "1.2.3.4"


async def test_flow_hassio_discovery(hass: HomeAssistant) -> None:
    """Test hassio discovery flow works."""
    result = await hass.config_entries.flow.async_init(
        DECONZ_DOMAIN,
        data=HassioServiceInfo(
            config={
                "addon": "Mock Addon",
                CONF_HOST: "mock-deconz",
                CONF_PORT: 80,
                CONF_SERIAL: BRIDGE_ID,
                CONF_API_KEY: API_KEY,
            },
            name="Mock Addon",
            slug="deconz",
            uuid="1234",
        ),
        context={"source": SOURCE_HASSIO},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "hassio_confirm"
    assert result["description_placeholders"] == {"addon": "Mock Addon"}

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert (
        flows[0].get("context", {}).get("configuration_url") == HASSIO_CONFIGURATION_URL
    )

    with patch(
        "homeassistant.components.deconz.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data == {
        CONF_HOST: "mock-deconz",
        CONF_PORT: 80,
        CONF_API_KEY: API_KEY,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_hassio_discovery_update_configuration(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Test we can update an existing config entry."""
    with patch(
        "homeassistant.components.deconz.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DECONZ_DOMAIN,
            data=HassioServiceInfo(
                config={
                    CONF_HOST: "2.3.4.5",
                    CONF_PORT: 8080,
                    CONF_API_KEY: "updated",
                    CONF_SERIAL: BRIDGE_ID,
                },
                name="Mock Addon",
                slug="deconz",
                uuid="1234",
            ),
            context={"source": SOURCE_HASSIO},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry_setup.data[CONF_HOST] == "2.3.4.5"
    assert config_entry_setup.data[CONF_PORT] == 8080
    assert config_entry_setup.data[CONF_API_KEY] == "updated"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("config_entry_setup")
async def test_hassio_discovery_dont_update_configuration(hass: HomeAssistant) -> None:
    """Test we can update an existing config entry."""
    result = await hass.config_entries.flow.async_init(
        DECONZ_DOMAIN,
        data=HassioServiceInfo(
            config={
                CONF_HOST: "1.2.3.4",
                CONF_PORT: 80,
                CONF_API_KEY: API_KEY,
                CONF_SERIAL: BRIDGE_ID,
            },
            name="Mock Addon",
            slug="deconz",
            uuid="1234",
        ),
        context={"source": SOURCE_HASSIO},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_option_flow(
    hass: HomeAssistant, config_entry_setup: MockConfigEntry
) -> None:
    """Test config flow options."""
    result = await hass.config_entries.options.async_init(config_entry_setup.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "deconz_devices"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_ALLOW_CLIP_SENSOR: False,
            CONF_ALLOW_DECONZ_GROUPS: False,
            CONF_ALLOW_NEW_DEVICES: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_ALLOW_CLIP_SENSOR: False,
        CONF_ALLOW_DECONZ_GROUPS: False,
        CONF_ALLOW_NEW_DEVICES: False,
        CONF_MASTER_GATEWAY: True,
    }
