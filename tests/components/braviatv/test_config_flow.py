"""Define tests for the Bravia TV config flow."""

from unittest.mock import patch

from pybravia import (
    BraviaAuthError,
    BraviaConnectionError,
    BraviaError,
    BraviaNotSupported,
)
import pytest

from homeassistant.components.braviatv.const import (
    CONF_NICKNAME,
    CONF_USE_PSK,
    DOMAIN,
    NICKNAME_PREFIX,
)
from homeassistant.config_entries import SOURCE_SSDP, SOURCE_USER
from homeassistant.const import CONF_CLIENT_ID, CONF_HOST, CONF_MAC, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import instance_id
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_MODEL_NAME,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

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

BRAVIA_SSDP = SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="mock_st",
    ssdp_location="http://bravia-host:52323/dmr.xml",
    upnp={
        ATTR_UPNP_UDN: "uuid:1234",
        ATTR_UPNP_FRIENDLY_NAME: "Living TV",
        ATTR_UPNP_MODEL_NAME: "KE-55XH9096",
        "X_ScalarWebAPI_DeviceInfo": {
            "X_ScalarWebAPI_ServiceList": {
                "X_ScalarWebAPI_ServiceType": [
                    "guide",
                    "system",
                    "audio",
                    "avContent",
                    "videoScreen",
                ],
            },
        },
    },
)

FAKE_BRAVIA_SSDP = SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="mock_st",
    ssdp_location="http://soundbar-host:52323/dmr.xml",
    upnp={
        ATTR_UPNP_UDN: "uuid:1234",
        ATTR_UPNP_FRIENDLY_NAME: "Sony Audio Device",
        ATTR_UPNP_MODEL_NAME: "HT-S700RF",
        "X_ScalarWebAPI_DeviceInfo": {
            "X_ScalarWebAPI_ServiceList": {
                "X_ScalarWebAPI_ServiceType": ["guide", "system", "audio", "avContent"],
            },
        },
    },
)

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_ssdp_discovery(hass: HomeAssistant) -> None:
    """Test that the device is discovered."""
    uuid = await instance_id.async_get(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=BRAVIA_SSDP,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    with (
        patch("pybravia.BraviaClient.connect"),
        patch("pybravia.BraviaClient.pair"),
        patch("pybravia.BraviaClient.set_wol_mode"),
        patch(
            "pybravia.BraviaClient.get_system_info",
            return_value=BRAVIA_SYSTEM_INFO,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "authorize"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_USE_PSK: False}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pin"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PIN: "1234"}
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].unique_id == "very_unique_string"
        assert result["title"] == "TV-Model"
        assert result["data"] == {
            CONF_HOST: "bravia-host",
            CONF_PIN: "1234",
            CONF_USE_PSK: False,
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
            CONF_CLIENT_ID: uuid,
            CONF_NICKNAME: f"{NICKNAME_PREFIX} {uuid[:6]}",
        }


async def test_ssdp_discovery_fake(hass: HomeAssistant) -> None:
    """Test that not Bravia device is not discovered."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=FAKE_BRAVIA_SSDP,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_bravia_device"


async def test_ssdp_discovery_exist(hass: HomeAssistant) -> None:
    """Test that the existed device is not discovered."""
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

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=BRAVIA_SSDP,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_invalid_host(hass: HomeAssistant) -> None:
    """Test that errors are shown when the host is invalid."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: "invalid/host"}
    )

    assert result["errors"] == {CONF_HOST: "invalid_host"}


@pytest.mark.parametrize(
    ("side_effect", "error_message"),
    [
        (BraviaAuthError, "invalid_auth"),
        (BraviaNotSupported, "unsupported_model"),
        (BraviaConnectionError, "cannot_connect"),
    ],
)
async def test_pin_form_error(hass: HomeAssistant, side_effect, error_message) -> None:
    """Test that PIN form errors are correct."""
    with (
        patch(
            "pybravia.BraviaClient.connect",
            side_effect=side_effect,
        ),
        patch("pybravia.BraviaClient.pair"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: "bravia-host"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_USE_PSK: False}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PIN: "1234"}
        )

        assert result["errors"] == {"base": error_message}


@pytest.mark.parametrize(
    ("side_effect", "error_message"),
    [
        (BraviaAuthError, "invalid_auth"),
        (BraviaNotSupported, "unsupported_model"),
        (BraviaConnectionError, "cannot_connect"),
    ],
)
async def test_psk_form_error(hass: HomeAssistant, side_effect, error_message) -> None:
    """Test that PSK form errors are correct."""
    with patch(
        "pybravia.BraviaClient.connect",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: "bravia-host"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_USE_PSK: True}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PIN: "mypsk"}
        )

        assert result["errors"] == {"base": error_message}


async def test_no_ip_control(hass: HomeAssistant) -> None:
    """Test that error are shown when IP Control is disabled on the TV."""
    with patch("pybravia.BraviaClient.pair", side_effect=BraviaError):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: "bravia-host"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_USE_PSK: False}
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_ip_control"


async def test_duplicate_error(hass: HomeAssistant) -> None:
    """Test that error are shown when duplicates are added."""
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

    with (
        patch("pybravia.BraviaClient.connect"),
        patch("pybravia.BraviaClient.pair"),
        patch("pybravia.BraviaClient.set_wol_mode"),
        patch(
            "pybravia.BraviaClient.get_system_info",
            return_value=BRAVIA_SYSTEM_INFO,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: "bravia-host"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_USE_PSK: False}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PIN: "1234"}
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test that entry is added correctly with PIN auth."""
    uuid = await instance_id.async_get(hass)

    with (
        patch("pybravia.BraviaClient.connect"),
        patch("pybravia.BraviaClient.pair"),
        patch("pybravia.BraviaClient.set_wol_mode"),
        patch(
            "pybravia.BraviaClient.get_system_info",
            return_value=BRAVIA_SYSTEM_INFO,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: "bravia-host"}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "authorize"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_USE_PSK: False}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pin"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PIN: "1234"}
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].unique_id == "very_unique_string"
        assert result["title"] == "TV-Model"
        assert result["data"] == {
            CONF_HOST: "bravia-host",
            CONF_PIN: "1234",
            CONF_USE_PSK: False,
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
            CONF_CLIENT_ID: uuid,
            CONF_NICKNAME: f"{NICKNAME_PREFIX} {uuid[:6]}",
        }


async def test_create_entry_psk(hass: HomeAssistant) -> None:
    """Test that entry is added correctly with PSK auth."""
    with (
        patch("pybravia.BraviaClient.connect"),
        patch("pybravia.BraviaClient.set_wol_mode"),
        patch(
            "pybravia.BraviaClient.get_system_info",
            return_value=BRAVIA_SYSTEM_INFO,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={CONF_HOST: "bravia-host"}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "authorize"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_USE_PSK: True}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "psk"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PIN: "mypsk"}
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].unique_id == "very_unique_string"
        assert result["title"] == "TV-Model"
        assert result["data"] == {
            CONF_HOST: "bravia-host",
            CONF_PIN: "mypsk",
            CONF_USE_PSK: True,
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
        }


@pytest.mark.parametrize(
    ("use_psk", "new_pin"),
    [
        (True, "7777"),
        (False, "newpsk"),
    ],
)
async def test_reauth_successful(hass: HomeAssistant, use_psk, new_pin) -> None:
    """Test that the reauthorization is successful."""
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
    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "authorize"

    with (
        patch("pybravia.BraviaClient.connect"),
        patch(
            "pybravia.BraviaClient.get_power_status",
            return_value="active",
        ),
        patch(
            "pybravia.BraviaClient.get_external_status",
            return_value=BRAVIA_SOURCES,
        ),
        patch(
            "pybravia.BraviaClient.send_rest_req",
            return_value={},
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_USE_PSK: use_psk}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PIN: new_pin}
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert config_entry.data[CONF_PIN] == new_pin
