"""Tests for the Netgear config flow."""
import logging
from unittest.mock import Mock, patch

from pynetgear import DEFAULT_HOST, DEFAULT_PORT, DEFAULT_USER
import pytest

from homeassistant import data_entry_flow
from homeassistant.components import ssdp
from homeassistant.components.netgear.const import CONF_CONSIDER_HOME, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_SSDP, SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
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
SSDP_URL = f"http://{HOST}:{PORT}/rootDesc.xml"
SSDP_URL_SLL = f"https://{HOST}:{PORT}/rootDesc.xml"


@pytest.fixture(name="service")
def mock_controller_service():
    """Mock a successful service."""
    with patch(
        "homeassistant.components.netgear.async_setup_entry", return_value=True
    ), patch("homeassistant.components.netgear.router.Netgear") as service_mock:
        service_mock.return_value.get_info = Mock(return_value=ROUTER_INFOS)
        yield service_mock


@pytest.fixture(name="service_failed")
def mock_controller_service_failed():
    """Mock a failed service."""
    with patch("homeassistant.components.netgear.router.Netgear") as service_mock:
        service_mock.return_value.login = Mock(return_value=None)
        service_mock.return_value.get_info = Mock(return_value=None)
        yield service_mock


async def test_user(hass, service):
    """Test user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
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
    assert result["data"].get(CONF_HOST) == HOST
    assert result["data"].get(CONF_PORT) == PORT
    assert result["data"].get(CONF_SSL) == SSL
    assert result["data"].get(CONF_USERNAME) == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD


async def test_import_required(hass, service):
    """Test import step, with required config only."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == SERIAL
    assert result["title"] == TITLE
    assert result["data"].get(CONF_HOST) == DEFAULT_HOST
    assert result["data"].get(CONF_PORT) == DEFAULT_PORT
    assert result["data"].get(CONF_SSL) is False
    assert result["data"].get(CONF_USERNAME) == DEFAULT_USER
    assert result["data"][CONF_PASSWORD] == PASSWORD


async def test_import_required_login_failed(hass, service_failed):
    """Test import step, with required config only, while wrong password or connection issue."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "config"}


async def test_import_all(hass, service):
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
    assert result["data"].get(CONF_HOST) == HOST
    assert result["data"].get(CONF_PORT) == PORT
    assert result["data"].get(CONF_SSL) == SSL
    assert result["data"].get(CONF_USERNAME) == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD


async def test_import_all_connection_failed(hass, service_failed):
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


async def test_abort_if_already_setup(hass, service):
    """Test we abort if the router is already setup."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PASSWORD: PASSWORD},
        unique_id=SERIAL,
    ).add_to_hass(hass)

    # Should fail, same SERIAL (import)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    # Should fail, same SERIAL (flow)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_ssdp_already_configured(hass):
    """Test ssdp abort when the router is already configured."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PASSWORD: PASSWORD},
        unique_id=SERIAL,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data={
            ssdp.ATTR_SSDP_LOCATION: SSDP_URL_SLL,
            ssdp.ATTR_UPNP_MODEL_NUMBER: "RBR20",
            ssdp.ATTR_UPNP_PRESENTATION_URL: URL,
            ssdp.ATTR_UPNP_SERIAL: SERIAL,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_ssdp(hass, service):
    """Test ssdp step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data={
            ssdp.ATTR_SSDP_LOCATION: SSDP_URL,
            ssdp.ATTR_UPNP_MODEL_NUMBER: "RBR20",
            ssdp.ATTR_UPNP_PRESENTATION_URL: URL,
            ssdp.ATTR_UPNP_SERIAL: SERIAL,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == SERIAL
    assert result["title"] == TITLE
    assert result["data"].get(CONF_HOST) == HOST
    assert result["data"].get(CONF_PORT) == PORT
    assert result["data"].get(CONF_SSL) == SSL
    assert result["data"].get(CONF_USERNAME) == DEFAULT_USER
    assert result["data"][CONF_PASSWORD] == PASSWORD


async def test_options_flow(hass, service):
    """Test specifying non default settings using options flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PASSWORD: PASSWORD},
        unique_id=SERIAL,
        title=TITLE,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_CONSIDER_HOME: 1800,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert config_entry.options == {
        CONF_CONSIDER_HOME: 1800,
    }
