"""Tests for the Netgear config flow."""
import logging
from unittest.mock import Mock, patch

import pytest

from homeassistant import data_entry_flow
from homeassistant.components import ssdp
from homeassistant.components.netgear.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_SSDP, SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
    CONF_USERNAME,
)

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)

URL = "http://routerlogin.net"
SERIAL = "5ER1AL0000001"

ROUTER_INFOS = {
    "Description": "Netgear Smart Wizard 3.0, specification 1.6 version",
    "SignalStrength": "-4",
    "SmartAgentversion": "3.0",
    "FirewallVersion": "net-wall 2.0",
    "VPNVersion": None,
    "OthersoftwareVersion": "N/A",
    "Hardwareversion": "N/A",
    "Otherhardwareversion": "N/A",
    "FirstUseDate": "Sunday, 30 Sep 2007 01:10:03",
    "DeviceMode": "0",
    "ModelName": "RBR20",
    "SerialNumber": SERIAL,
    "Firmwareversion": "V2.3.5.26",
    "DeviceName": "Desk",
    "DeviceNameUserSet": "true",
    "FirmwareDLmethod": "HTTPS",
    "FirmwareLastUpdate": "2019_10.5_18:42:58",
    "FirmwareLastChecked": "2020_5.3_1:33:0",
    "DeviceModeCapability": "0;1",
}
TITLE = f"{ROUTER_INFOS['ModelName']} - {ROUTER_INFOS['DeviceName']}"

HOST = "10.0.0.1"
SERIAL_2 = "5ER1AL0000002"
PORT = 80
SSL = False
USERNAME = "Home_Assistant"
PASSWORD = "password"


@pytest.fixture(name="autodetect_url")
def mock_controller_autodetect_url():
    """Mock a successful autodetect."""
    with patch(
        "homeassistant.components.netgear.config_flow.autodetect_url"
    ) as service_mock:
        service_mock.return_value = URL
        yield service_mock


@pytest.fixture(name="autodetect_url_not_found")
def mock_controller_autodetect_url_not_found():
    """Mock a non successful autodetect."""
    with patch(
        "homeassistant.components.netgear.config_flow.autodetect_url"
    ) as service_mock:
        service_mock.return_value = None
        yield service_mock


@pytest.fixture(name="service")
def mock_controller_service():
    """Mock a successful service."""
    with patch("homeassistant.components.netgear.config_flow.Netgear") as service_mock:
        service_mock.return_value.get_info = Mock(return_value=ROUTER_INFOS)
        yield service_mock


@pytest.fixture(name="service_failed")
def mock_controller_service_failed():
    """Mock a failed service."""
    with patch("homeassistant.components.netgear.config_flow.Netgear") as service_mock:
        service_mock.return_value.login = Mock(return_value=None)
        service_mock.return_value.get_info = Mock(return_value=None)
        yield service_mock


async def _discover_step_user(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "discover"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    return result


async def test_discover(hass, autodetect_url, service):
    """Test discover step."""
    result = await _discover_step_user(hass)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"


async def test_user_required(hass, autodetect_url, service):
    """Test user step."""
    result = await _discover_step_user(hass)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"

    # test with required only
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == SERIAL
    assert result["title"] == TITLE
    assert result["data"].get(CONF_URL) == URL
    assert result["data"].get(CONF_HOST) is None
    assert result["data"].get(CONF_PORT) is None
    assert result["data"].get(CONF_SSL) is None
    assert result["data"].get(CONF_USERNAME) is None
    assert result["data"][CONF_PASSWORD] == PASSWORD


async def test_user_url_not_found(hass, autodetect_url_not_found, service):
    """Test user step while autodetect_url did not find url."""
    result = await _discover_step_user(hass)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # Have to provide all config
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_SSL: SSL,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == SERIAL
    assert result["title"] == TITLE
    assert result["data"].get(CONF_URL) is None
    assert result["data"].get(CONF_HOST) == HOST
    assert result["data"].get(CONF_PORT) == PORT
    assert result["data"].get(CONF_SSL) == SSL
    assert result["data"].get(CONF_USERNAME) == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD


async def test_import_required(hass, autodetect_url, service):
    """Test import step, with required config only."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == SERIAL
    assert result["title"] == TITLE
    assert result["data"].get(CONF_URL) == URL
    assert result["data"].get(CONF_HOST) is None
    assert result["data"].get(CONF_PORT) is None
    assert result["data"].get(CONF_SSL) is None
    assert result["data"].get(CONF_USERNAME) is None
    assert result["data"][CONF_PASSWORD] == PASSWORD


async def test_import_required_login_failed(hass, autodetect_url, service_failed):
    """Test import step, with required config only, while wrong password."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"
    assert result["errors"] == {"base": "config"}


async def test_import_all(hass, autodetect_url, service):
    """Test import step, with all config provided."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_SSL: SSL,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == SERIAL
    assert result["title"] == TITLE
    assert result["data"].get(CONF_URL) is None
    assert result["data"].get(CONF_HOST) == HOST
    assert result["data"].get(CONF_PORT) == PORT
    assert result["data"].get(CONF_SSL) == SSL
    assert result["data"].get(CONF_USERNAME) == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD


async def test_import_all_connection_failed(hass, autodetect_url, service_failed):
    """Test import step, with all config provided, while wrong host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_SSL: SSL,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "config"}


async def test_abort_if_already_setup(hass, autodetect_url, service):
    """Test we abort if the router is already setup."""
    MockConfigEntry(
        domain=DOMAIN, data={CONF_PASSWORD: PASSWORD}, unique_id=SERIAL,
    ).add_to_hass(hass)

    # Should fail, same SERIAL (import)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    # Should fail, same SERIAL (flow)
    result = await _discover_step_user(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_form_ssdp_already_configured(hass):
    """Test ssdp abort when the router is already configured."""
    MockConfigEntry(
        domain=DOMAIN, data={CONF_PASSWORD: PASSWORD}, unique_id=SERIAL,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data={
            ssdp.ATTR_SSDP_LOCATION: "http://10.0.0.1:5555/rootDesc.xml",
            ssdp.ATTR_UPNP_MODEL_NUMBER: "RBR20",
            ssdp.ATTR_UPNP_PRESENTATION_URL: URL,
            ssdp.ATTR_UPNP_SERIAL: SERIAL,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_form_ssdp(hass, autodetect_url, service):
    """Test ssdp step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data={
            ssdp.ATTR_SSDP_LOCATION: "http://10.0.0.1:5555/rootDesc.xml",
            ssdp.ATTR_UPNP_MODEL_NUMBER: "RBR20",
            ssdp.ATTR_UPNP_PRESENTATION_URL: URL,
            ssdp.ATTR_UPNP_SERIAL: SERIAL,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == SERIAL
    assert result["title"] == TITLE
    assert result["data"].get(CONF_URL) == URL
    assert result["data"].get(CONF_HOST) is None
    assert result["data"].get(CONF_PORT) is None
    assert result["data"].get(CONF_SSL) is None
    assert result["data"].get(CONF_USERNAME) is None
    assert result["data"][CONF_PASSWORD] == PASSWORD
