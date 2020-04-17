"""Tests for the Synology DSM config flow."""
import logging
from unittest.mock import MagicMock, Mock, patch

import pytest

from homeassistant import data_entry_flow, setup
from homeassistant.components import ssdp
from homeassistant.components.synology_dsm.const import (
    CONF_VOLUMES,
    DEFAULT_DSM_VERSION,
    DEFAULT_PORT,
    DEFAULT_PORT_SSL,
    DEFAULT_SSL,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_SSDP, SOURCE_USER
from homeassistant.const import (
    CONF_API_VERSION,
    CONF_DISKS,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


HOST = "nas.meontheinternet.com"
SERIAL = "mySerial"
HOST_2 = "nas.worldwide.me"
SERIAL_2 = "mySerial2"
PORT = 1234
SSL = True
USERNAME = "Home_Assistant"
PASSWORD = "password"


@pytest.fixture(name="service")
def mock_controller_service():
    """Mock a successful service."""
    with patch(
        "homeassistant.components.synology_dsm.config_flow.SynologyDSM"
    ) as service_mock:
        service_mock.return_value.information.serial = SERIAL
        service_mock.return_value.utilisation.cpu_user_load = 1
        service_mock.return_value.storage.disks_ids = []
        service_mock.return_value.storage.volumes_ids = []
        yield service_mock


@pytest.fixture(name="service_login_failed")
def mock_controller_service_login_failed():
    """Mock a failed login."""
    with patch(
        "homeassistant.components.synology_dsm.config_flow.SynologyDSM"
    ) as service_mock:
        service_mock.return_value.login = Mock(return_value=False)
        yield service_mock


@pytest.fixture(name="service_failed")
def mock_controller_service_failed():
    """Mock a failed service."""
    with patch(
        "homeassistant.components.synology_dsm.config_flow.SynologyDSM"
    ) as service_mock:
        service_mock.return_value.information.serial = None
        service_mock.return_value.utilisation.cpu_user_load = None
        service_mock.return_value.storage.disks_ids = None
        service_mock.return_value.storage.volumes_ids = None
        yield service_mock


async def test_user(hass: HomeAssistantType, service: MagicMock):
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=None
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # test with all provided
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_SSL: SSL,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_API_VERSION: 5,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == SERIAL
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT
    assert result["data"][CONF_SSL] == SSL
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_API_VERSION] == 5
    assert result["data"].get(CONF_DISKS) is None
    assert result["data"].get(CONF_VOLUMES) is None

    service.return_value.information.serial = SERIAL_2
    # test without port + False SSL
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: HOST,
            CONF_SSL: False,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == SERIAL_2
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == DEFAULT_PORT
    assert not result["data"][CONF_SSL]
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_API_VERSION] == DEFAULT_DSM_VERSION
    assert result["data"].get(CONF_DISKS) is None
    assert result["data"].get(CONF_VOLUMES) is None


async def test_import(hass: HomeAssistantType, service: MagicMock):
    """Test import step."""
    # import with minimum setup
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: HOST, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == SERIAL
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == DEFAULT_PORT_SSL
    assert result["data"][CONF_SSL] == DEFAULT_SSL
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_API_VERSION] == DEFAULT_DSM_VERSION
    assert result["data"].get(CONF_DISKS) is None
    assert result["data"].get(CONF_VOLUMES) is None

    service.return_value.information.serial = SERIAL_2
    # import with all
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: HOST_2,
            CONF_PORT: PORT,
            CONF_SSL: SSL,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_API_VERSION: 5,
            CONF_DISKS: ["sda", "sdb", "sdc"],
            CONF_VOLUMES: ["volume_1"],
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == SERIAL_2
    assert result["title"] == HOST_2
    assert result["data"][CONF_HOST] == HOST_2
    assert result["data"][CONF_PORT] == PORT
    assert result["data"][CONF_SSL] == SSL
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_API_VERSION] == 5
    assert result["data"][CONF_DISKS] == ["sda", "sdb", "sdc"]
    assert result["data"][CONF_VOLUMES] == ["volume_1"]


async def test_abort_if_already_setup(hass: HomeAssistantType, service: MagicMock):
    """Test we abort if the account is already setup."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: HOST, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        unique_id=SERIAL,
    ).add_to_hass(hass)

    # Should fail, same HOST:PORT (import)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: HOST, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    # Should fail, same HOST:PORT (flow)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_login_failed(hass: HomeAssistantType, service_login_failed: MagicMock):
    """Test when we have errors during connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_USERNAME: "login"}


async def test_missing_data_after_login(
    hass: HomeAssistantType, service_failed: MagicMock
):
    """Test when we have errors during connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "missing_data"}


async def test_form_ssdp(hass: HomeAssistantType, service: MagicMock):
    """Test we can setup from ssdp."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data={
            ssdp.ATTR_SSDP_LOCATION: "http://192.168.1.5:5000",
            ssdp.ATTR_UPNP_FRIENDLY_NAME: "mydsm",
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "link"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "192.168.1.5"
    assert result["data"][CONF_HOST] == "192.168.1.5"
    assert result["data"][CONF_PORT] == 5001
    assert result["data"][CONF_SSL] == DEFAULT_SSL
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_API_VERSION] == DEFAULT_DSM_VERSION
    assert result["data"].get(CONF_DISKS) is None
    assert result["data"].get(CONF_VOLUMES) is None
