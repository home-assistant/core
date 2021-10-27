"""Test the songpal config flow."""
import copy
from unittest.mock import patch

from homeassistant.components import ssdp
from homeassistant.components.songpal.const import CONF_ENDPOINT, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_SSDP, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from . import (
    CONF_DATA,
    ENDPOINT,
    FRIENDLY_NAME,
    HOST,
    MODEL,
    _create_mocked_device,
    _patch_config_flow_device,
)

from tests.common import MockConfigEntry

UDN = "uuid:1234"

SSDP_DATA = {
    ssdp.ATTR_UPNP_UDN: UDN,
    ssdp.ATTR_UPNP_FRIENDLY_NAME: FRIENDLY_NAME,
    ssdp.ATTR_SSDP_LOCATION: f"http://{HOST}:52323/dmr.xml",
    "X_ScalarWebAPI_DeviceInfo": {
        "X_ScalarWebAPI_BaseURL": ENDPOINT,
        "X_ScalarWebAPI_ServiceList": {
            "X_ScalarWebAPI_ServiceType": ["guide", "system", "audio", "avContent"],
        },
    },
}


def _flow_next(hass, flow_id):
    return next(
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == flow_id
    )


def _patch_setup():
    return patch(
        "homeassistant.components.songpal.async_setup_entry",
        return_value=True,
    )


async def test_flow_ssdp(hass):
    """Test working ssdp flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SSDP_DATA,
    )
    assert result["type"] == "form"
    assert result["step_id"] == "init"
    assert result["description_placeholders"] == {
        CONF_NAME: FRIENDLY_NAME,
        CONF_HOST: HOST,
    }
    flow = _flow_next(hass, result["flow_id"])
    assert flow["context"]["unique_id"] == UDN

    with _patch_setup():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == FRIENDLY_NAME
        assert result["data"] == CONF_DATA


async def test_flow_user(hass):
    """Test working user initialized flow."""
    mocked_device = _create_mocked_device()

    with _patch_config_flow_device(mocked_device), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] is None
        _flow_next(hass, result["flow_id"])

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_ENDPOINT: ENDPOINT},
        )
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == MODEL
        assert result["data"] == {
            CONF_NAME: MODEL,
            CONF_ENDPOINT: ENDPOINT,
        }

    mocked_device.get_supported_methods.assert_called_once()
    mocked_device.get_interface_information.assert_called_once()


async def test_flow_import(hass):
    """Test working import flow."""
    mocked_device = _create_mocked_device()

    with _patch_config_flow_device(mocked_device), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=CONF_DATA
        )
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == FRIENDLY_NAME
        assert result["data"] == CONF_DATA

    mocked_device.get_supported_methods.assert_called_once()
    mocked_device.get_interface_information.assert_not_called()


async def test_flow_import_without_name(hass):
    """Test import flow without optional name."""
    mocked_device = _create_mocked_device()

    with _patch_config_flow_device(mocked_device), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_ENDPOINT: ENDPOINT}
        )
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == MODEL
        assert result["data"] == {CONF_NAME: MODEL, CONF_ENDPOINT: ENDPOINT}

    mocked_device.get_supported_methods.assert_called_once()
    mocked_device.get_interface_information.assert_called_once()


def _create_mock_config_entry(hass):
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="uuid:0000",
        data=CONF_DATA,
    ).add_to_hass(hass)


async def test_ssdp_bravia(hass):
    """Test discovering a bravia TV."""
    ssdp_data = copy.deepcopy(SSDP_DATA)
    ssdp_data["X_ScalarWebAPI_DeviceInfo"]["X_ScalarWebAPI_ServiceList"][
        "X_ScalarWebAPI_ServiceType"
    ].append("videoScreen")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=ssdp_data,
    )
    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "not_songpal_device"


async def test_sddp_exist(hass):
    """Test discovering existed device."""
    _create_mock_config_entry(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SSDP_DATA,
    )
    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_user_exist(hass):
    """Test user adding existed device."""
    mocked_device = _create_mocked_device()
    _create_mock_config_entry(hass)

    with _patch_config_flow_device(mocked_device):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
        )
        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"

    mocked_device.get_supported_methods.assert_called_once()
    mocked_device.get_interface_information.assert_called_once()


async def test_import_exist(hass):
    """Test importing existed device."""
    mocked_device = _create_mocked_device()
    _create_mock_config_entry(hass)

    with _patch_config_flow_device(mocked_device):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=CONF_DATA
        )
        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"

    mocked_device.get_supported_methods.assert_called_once()
    mocked_device.get_interface_information.assert_not_called()


async def test_user_invalid(hass):
    """Test using adding invalid config."""
    mocked_device = _create_mocked_device(True)
    _create_mock_config_entry(hass)

    with _patch_config_flow_device(mocked_device):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_DATA
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}

    mocked_device.get_supported_methods.assert_called_once()
    mocked_device.get_interface_information.assert_not_called()


async def test_import_invalid(hass):
    """Test importing invalid config."""
    mocked_device = _create_mocked_device(True)
    _create_mock_config_entry(hass)

    with _patch_config_flow_device(mocked_device):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=CONF_DATA
        )
        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "cannot_connect"

    mocked_device.get_supported_methods.assert_called_once()
    mocked_device.get_interface_information.assert_not_called()
