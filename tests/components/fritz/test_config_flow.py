"""Tests for Fritz!Tools config flow."""

from copy import deepcopy
import dataclasses
from typing import Any
from unittest.mock import patch

from fritzconnection.core.exceptions import (
    FritzAuthorizationError,
    FritzConnectionException,
    FritzSecurityError,
)
import pytest

from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
    DEFAULT_CONSIDER_HOME,
)
from homeassistant.components.fritz.config_flow import (
    _host_from_ssdp,
    _host_from_ssdp_usn,
    _is_link_local_host,
    _is_placeholder_unique_id,
    _parse_device_uuid,
    _uuid_from_discovery,
    _uuid_from_ssdp_usn,
    _uuid_from_upnp_udn,
)
from homeassistant.components.fritz.const import (
    CONF_FEATURE_DEVICE_TRACKING,
    CONF_OLD_DISCOVERY,
    DOMAIN,
    ERROR_AUTH_INVALID,
    ERROR_CANNOT_CONNECT,
    ERROR_UNKNOWN,
    ERROR_UPNP_NOT_CONFIGURED,
    FRITZ_AUTH_EXCEPTIONS,
)
from homeassistant.config_entries import SOURCE_SSDP, SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_MODEL_NAME,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

from .conftest import FritzConnectionMock
from .const import (
    MOCK_FB_SERVICES,
    MOCK_FIRMWARE_INFO,
    MOCK_FRITZ_OTHER_DEVICE_UUID,
    MOCK_FRITZ_SSDP_DEVICE_UUID,
    MOCK_FRITZ_SSDP_UDN,
    MOCK_FRITZ_SSDP_USN,
    MOCK_IPS,
    MOCK_REQUEST,
    MOCK_SSDP_DATA,
    MOCK_SSDP_DATA_NO_UDN,
    MOCK_USER_DATA,
    MOCK_USER_INPUT_SIMPLE,
)

from tests.common import MockConfigEntry


def _flow_context(hass: HomeAssistant, flow_id: str) -> dict[str, Any]:
    """Return context from an in-progress config flow (public API)."""
    for progress in hass.config_entries.flow.async_progress():
        if progress["flow_id"] == flow_id:
            return progress["context"]
    pytest.fail(f"Flow {flow_id} not in progress")


def _flow_unique_id(hass: HomeAssistant, flow_id: str) -> str | None:
    """Return unique_id from an in-progress config flow (public API)."""
    return _flow_context(hass, flow_id).get("unique_id")


def test_parse_device_uuid() -> None:
    """Test UUID parsing and normalization."""
    assert _parse_device_uuid(f"  {MOCK_FRITZ_SSDP_DEVICE_UUID}  ") == (
        MOCK_FRITZ_SSDP_DEVICE_UUID
    )
    assert _parse_device_uuid("") is None
    assert _parse_device_uuid("not-a-uuid") is None


def test_uuid_from_upnp_udn() -> None:
    """Test UUID extraction from UPnP UDN."""
    assert _uuid_from_upnp_udn(MOCK_FRITZ_SSDP_UDN) == MOCK_FRITZ_SSDP_DEVICE_UUID
    assert _uuid_from_upnp_udn("uuid:not-a-uuid") is None


def test_uuid_from_ssdp_usn() -> None:
    """Test UUID extraction from SSDP USN."""
    assert _uuid_from_ssdp_usn(MOCK_FRITZ_SSDP_USN) == MOCK_FRITZ_SSDP_DEVICE_UUID
    assert _uuid_from_ssdp_usn("mock_usn") is None


def test_host_from_ssdp_location() -> None:
    """Test host extraction from SSDP location."""
    assert _host_from_ssdp(MOCK_SSDP_DATA) == MOCK_IPS["fritz.box"]


def test_host_from_ssdp_returns_none() -> None:
    """Test host extraction when location and headers are missing."""
    discovery = SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="mock_st",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "fake_name"},
    )
    assert _host_from_ssdp(discovery) is None


def test_host_from_ssdp_returns_none_without_usn() -> None:
    """Test host extraction when SSDP provides no USN."""
    discovery = SsdpServiceInfo(
        ssdp_usn="",
        ssdp_st="mock_st",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "fake_name"},
    )
    assert _host_from_ssdp(discovery) is None


def test_host_from_ssdp_skips_non_string_header_location() -> None:
    """Test host extraction ignores non-string header location values."""
    discovery = SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="mock_st",
        ssdp_headers={"location": 12345},
        upnp={ATTR_UPNP_FRIENDLY_NAME: "fake_name"},
    )
    assert _host_from_ssdp(discovery) is None


def test_host_from_ssdp_empty_location_hostname_uses_headers() -> None:
    """Test host uses headers when location has no hostname."""
    discovery = SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="mock_st",
        ssdp_location="http:///no-hostname",
        ssdp_headers={"location": f"https://{MOCK_IPS['fritz.box']}:12345/test"},
        upnp={ATTR_UPNP_FRIENDLY_NAME: "fake_name"},
    )
    assert _host_from_ssdp(discovery) == MOCK_IPS["fritz.box"]


def test_host_from_ssdp_fritz_box_from_usn() -> None:
    """Test host falls back to fritz.box when advertised in USN only."""
    discovery = SsdpServiceInfo(
        ssdp_usn="uuid:device-1::upnp:rootdevice://fritz.box",
        ssdp_st="mock_st",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "fake_name"},
    )
    assert _host_from_ssdp(discovery) == "fritz.box"


def test_host_from_ssdp_usn() -> None:
    """Test USN host extraction requires an exact fritz.box URL hostname."""
    assert (
        _host_from_ssdp_usn("uuid:device-1::upnp:rootdevice://fritz.box") == "fritz.box"
    )
    assert (
        _host_from_ssdp_usn("uuid:device-1::upnp:rootdevice://FRITZ.box") == "fritz.box"
    )
    assert _host_from_ssdp_usn("uuid:device-1::upnp:rootdevice") is None
    assert _host_from_ssdp_usn("uuid:device-1::vendor:my-fritz.box-repeater") is None
    assert _host_from_ssdp_usn("uuid:device-1::upnp://fritz.box.local") is None
    assert _host_from_ssdp_usn("uuid:device-1::vendor://fritz.box.example/path") is None
    assert (
        _host_from_ssdp_usn("uuid:device-1::upnp:rootdevice://fritz.box::suffix")
        == "fritz.box"
    )


def test_host_from_ssdp_location_value_error_uses_usn() -> None:
    """Test host falls back to USN when location URL parsing fails."""
    discovery = SsdpServiceInfo(
        ssdp_usn="uuid:device-1::upnp:rootdevice://fritz.box",
        ssdp_st="mock_st",
        ssdp_location="https://[invalid",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "fake_name"},
    )
    with patch(
        "homeassistant.components.fritz.config_flow.urlparse",
        side_effect=ValueError(),
    ):
        assert _host_from_ssdp(discovery) == "fritz.box"


def test_is_link_local_host() -> None:
    """Test link-local host detection."""
    assert _is_link_local_host("fritz.box") is False
    assert _is_link_local_host(MOCK_IPS["fritz.box"]) is False
    assert _is_link_local_host("fe80::1") is True
    assert _is_link_local_host("not-an-ip") is False


def test_is_placeholder_unique_id() -> None:
    """Test placeholder unique_id detection for SSDP migration."""
    assert _is_placeholder_unique_id(None, "192.168.1.1", "fritz.box") is True
    assert _is_placeholder_unique_id("192.168.1.1", "192.168.1.1", "fritz.box") is True
    assert _is_placeholder_unique_id("fritz.box", "192.168.1.1", "fritz.box") is True
    assert (
        _is_placeholder_unique_id(
            MOCK_FRITZ_OTHER_DEVICE_UUID, "192.168.1.1", "fritz.box"
        )
        is False
    )


def test_uuid_from_discovery_prefers_udn() -> None:
    """Test UUID from discovery prefers UPnP UDN over USN."""
    discovery = dataclasses.replace(
        MOCK_SSDP_DATA,
        ssdp_usn=MOCK_FRITZ_SSDP_USN,
        upnp={
            ATTR_UPNP_FRIENDLY_NAME: "fake_name",
            ATTR_UPNP_UDN: MOCK_FRITZ_SSDP_UDN,
        },
    )
    assert _uuid_from_discovery(discovery) == MOCK_FRITZ_SSDP_DEVICE_UUID


def test_uuid_from_discovery_falls_back_to_usn() -> None:
    """Test UUID from discovery uses USN when UDN is missing."""
    assert _uuid_from_discovery(MOCK_SSDP_DATA_NO_UDN) is None
    discovery = dataclasses.replace(
        MOCK_SSDP_DATA_NO_UDN,
        ssdp_usn=MOCK_FRITZ_SSDP_USN,
    )
    assert _uuid_from_discovery(discovery) == MOCK_FRITZ_SSDP_DEVICE_UUID


async def test_ssdp_hostname_from_usn_only(hass: HomeAssistant, fc_class_mock) -> None:
    """Test SSDP flow uses fritz.box from USN and the device UUID from UDN."""
    discovery = SsdpServiceInfo(
        ssdp_usn="uuid:device-1::upnp:rootdevice://fritz.box",
        ssdp_st="mock_st",
        upnp={
            ATTR_UPNP_FRIENDLY_NAME: "fake_name",
            ATTR_UPNP_UDN: MOCK_FRITZ_SSDP_UDN,
        },
    )
    with (
        patch(
            "homeassistant.components.fritz.config_flow.FritzConnection",
            side_effect=fc_class_mock,
        ),
        patch(
            "homeassistant.components.fritz.config_flow.socket.gethostbyname",
            return_value=MOCK_IPS["fritz.box"],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=discovery
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert (
        _flow_context(hass, result["flow_id"])["configuration_url"]
        == "http://fritz.box"
    )
    assert _flow_unique_id(hass, result["flow_id"]) == MOCK_FRITZ_SSDP_DEVICE_UUID


async def test_ssdp_fritz_box_from_usn_without_uuid(
    hass: HomeAssistant, fc_class_mock
) -> None:
    """Test SSDP uses fritz.box host and host unique_id when no UUID is advertised."""
    discovery = SsdpServiceInfo(
        ssdp_usn="uuid:device-1::upnp:rootdevice://fritz.box",
        ssdp_st="mock_st",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "fake_name"},
    )
    with (
        patch(
            "homeassistant.components.fritz.config_flow.FritzConnection",
            side_effect=fc_class_mock,
        ),
        patch(
            "homeassistant.components.fritz.config_flow.socket.gethostbyname",
            return_value=MOCK_IPS["fritz.box"],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=discovery
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert (
        _flow_context(hass, result["flow_id"])["configuration_url"]
        == "http://fritz.box"
    )
    assert _flow_unique_id(hass, result["flow_id"]) == "fritz.box"


async def test_ssdp_already_configured_skips_migration_without_uuid(
    hass: HomeAssistant,
) -> None:
    """Test SSDP without UUID does not migrate a host placeholder unique_id."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_USER_DATA, CONF_HOST: "fritz.box"},
        unique_id="fritz.box",
    )
    mock_config.add_to_hass(hass)

    discovery = SsdpServiceInfo(
        ssdp_usn="uuid:device-1::upnp:rootdevice://fritz.box",
        ssdp_st="mock_st",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "fake_name"},
    )
    with patch(
        "homeassistant.components.fritz.config_flow.socket.gethostbyname",
        return_value=MOCK_IPS["fritz.box"],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=discovery
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config.unique_id == "fritz.box"


@pytest.mark.parametrize(
    ("user_input", "expected_config", "expected_options"),
    [
        (
            MOCK_USER_DATA,
            {
                CONF_HOST: "fake_host",
                CONF_PASSWORD: "fake_pass",
                CONF_USERNAME: "fake_user",
                CONF_PORT: 1234,
                CONF_SSL: False,
            },
            {
                CONF_OLD_DISCOVERY: False,
                CONF_CONSIDER_HOME: DEFAULT_CONSIDER_HOME.total_seconds(),
                CONF_FEATURE_DEVICE_TRACKING: True,
            },
        ),
        (
            MOCK_USER_INPUT_SIMPLE,
            {
                CONF_HOST: "fake_host",
                CONF_PASSWORD: "fake_pass",
                CONF_USERNAME: "fake_user",
                CONF_PORT: 49000,
                CONF_SSL: False,
            },
            {
                CONF_OLD_DISCOVERY: False,
                CONF_CONSIDER_HOME: DEFAULT_CONSIDER_HOME.total_seconds(),
                CONF_FEATURE_DEVICE_TRACKING: True,
            },
        ),
        (
            {
                **MOCK_USER_INPUT_SIMPLE,
                CONF_SSL: True,
                CONF_FEATURE_DEVICE_TRACKING: False,
            },
            {
                CONF_HOST: "fake_host",
                CONF_PASSWORD: "fake_pass",
                CONF_USERNAME: "fake_user",
                CONF_PORT: 49443,
                CONF_SSL: True,
            },
            {
                CONF_OLD_DISCOVERY: False,
                CONF_CONSIDER_HOME: DEFAULT_CONSIDER_HOME.total_seconds(),
                CONF_FEATURE_DEVICE_TRACKING: False,
            },
        ),
    ],
)
async def test_user(
    hass: HomeAssistant,
    fc_class_mock,
    user_input: dict,
    expected_config: dict,
    expected_options: dict,
) -> None:
    """Test starting a flow by user."""
    with (
        patch(
            "homeassistant.components.fritz.config_flow.FritzConnection",
            side_effect=fc_class_mock,
        ),
        patch(
            "homeassistant.components.fritz.coordinator.FritzBoxTools._update_device_info",
            return_value=MOCK_FIRMWARE_INFO,
        ),
        patch("homeassistant.components.fritz.async_setup_entry") as mock_setup_entry,
        patch(
            "requests.get",
        ) as mock_request_get,
        patch(
            "requests.post",
        ) as mock_request_post,
        patch(
            "homeassistant.components.fritz.config_flow.socket.gethostbyname",
            return_value=MOCK_IPS["fritz.box"],
        ),
    ):
        mock_request_get.return_value.status_code = 200
        mock_request_get.return_value.content = MOCK_REQUEST
        mock_request_post.return_value.status_code = 200
        mock_request_post.return_value.text = MOCK_REQUEST

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=user_input
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == expected_config
        assert result["options"] == expected_options
        assert not result["result"].unique_id

    assert mock_setup_entry.called


@pytest.mark.parametrize(
    ("user_input"),
    [(MOCK_USER_DATA), (MOCK_USER_INPUT_SIMPLE)],
)
async def test_user_already_configured(
    hass: HomeAssistant,
    fc_class_mock,
    user_input,
) -> None:
    """Test starting a flow by user with an already configured device."""

    mock_config = MockConfigEntry(domain=DOMAIN, data=user_input)
    mock_config.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.fritz.config_flow.FritzConnection",
            side_effect=fc_class_mock,
        ),
        patch(
            "homeassistant.components.fritz.coordinator.FritzBoxTools._update_device_info",
            return_value=MOCK_FIRMWARE_INFO,
        ),
        patch(
            "requests.get",
        ) as mock_request_get,
        patch(
            "requests.post",
        ) as mock_request_post,
        patch(
            "homeassistant.components.fritz.config_flow.socket.gethostbyname",
            return_value=MOCK_IPS["fritz.box"],
        ),
    ):
        mock_request_get.return_value.status_code = 200
        mock_request_get.return_value.content = MOCK_REQUEST
        mock_request_post.return_value.status_code = 200
        mock_request_post.return_value.text = MOCK_REQUEST

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_INPUT_SIMPLE
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "already_configured"


@pytest.mark.parametrize(
    "error",
    FRITZ_AUTH_EXCEPTIONS,
)
@pytest.mark.parametrize(
    ("user_input"),
    [(MOCK_USER_DATA), (MOCK_USER_INPUT_SIMPLE)],
)
async def test_exception_security(
    hass: HomeAssistant,
    error,
    user_input,
) -> None:
    """Test starting a flow by user with invalid credentials."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.fritz.config_flow.FritzConnection",
        side_effect=error,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=user_input
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == ERROR_AUTH_INVALID


@pytest.mark.parametrize(
    ("user_input"),
    [(MOCK_USER_DATA), (MOCK_USER_INPUT_SIMPLE)],
)
async def test_exception_connection(
    hass: HomeAssistant,
    user_input,
) -> None:
    """Test starting a flow by user with a connection error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.fritz.config_flow.FritzConnection",
        side_effect=FritzConnectionException,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=user_input
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == ERROR_CANNOT_CONNECT


@pytest.mark.parametrize(
    ("user_input"),
    [(MOCK_USER_DATA), (MOCK_USER_INPUT_SIMPLE)],
)
async def test_exception_unknown(hass: HomeAssistant, user_input) -> None:
    """Test starting a flow by user with an unknown exception."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.fritz.config_flow.FritzConnection",
        side_effect=OSError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=user_input
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == ERROR_UNKNOWN


async def test_reauth_successful(
    hass: HomeAssistant,
    fc_class_mock,
) -> None:
    """Test starting a reauthentication flow."""

    mock_config = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    mock_config.add_to_hass(hass)
    result = await mock_config.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "homeassistant.components.fritz.config_flow.FritzConnection",
            side_effect=fc_class_mock,
        ),
        patch(
            "homeassistant.components.fritz.coordinator.FritzBoxTools._update_device_info",
            return_value=MOCK_FIRMWARE_INFO,
        ),
        patch(
            "homeassistant.components.fritz.async_setup_entry",
        ) as mock_setup_entry,
        patch(
            "requests.get",
        ) as mock_request_get,
        patch(
            "requests.post",
        ) as mock_request_post,
    ):
        mock_request_get.return_value.status_code = 200
        mock_request_get.return_value.content = MOCK_REQUEST
        mock_request_post.return_value.status_code = 200
        mock_request_post.return_value.text = MOCK_REQUEST

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "other_fake_user",
                CONF_PASSWORD: "other_fake_password",
            },
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"

    assert mock_setup_entry.called


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (FritzAuthorizationError, ERROR_AUTH_INVALID),
        (FritzConnectionException, ERROR_CANNOT_CONNECT),
        (FritzSecurityError, ERROR_AUTH_INVALID),
    ],
)
async def test_reauth_not_successful(
    hass: HomeAssistant,
    fc_class_mock,
    side_effect,
    error,
) -> None:
    """Test starting a reauthentication flow but no connection found."""

    mock_config = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    mock_config.add_to_hass(hass)
    result = await mock_config.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.fritz.config_flow.FritzConnection",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "other_fake_user",
                CONF_PASSWORD: "other_fake_password",
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"]["base"] == error


@pytest.mark.parametrize(
    ("initial_config", "user_input", "expected_config"),
    [
        (
            MOCK_USER_DATA,
            {CONF_HOST: "host_a", CONF_PORT: 49000, CONF_SSL: False},
            {CONF_HOST: "host_a", CONF_PORT: 49000, CONF_SSL: False},
        ),
        (
            MOCK_USER_DATA,
            {CONF_HOST: "host_a", CONF_PORT: 49443, CONF_SSL: True},
            {CONF_HOST: "host_a", CONF_PORT: 49443, CONF_SSL: True},
        ),
        (
            MOCK_USER_DATA,
            {CONF_HOST: "host_a", CONF_PORT: 12345, CONF_SSL: True},
            {CONF_HOST: "host_a", CONF_PORT: 12345, CONF_SSL: True},
        ),
        (
            MOCK_USER_DATA,
            {CONF_HOST: "host_b", CONF_SSL: False},
            {CONF_HOST: "host_b", CONF_PORT: 1234, CONF_SSL: False},
        ),
        (
            MOCK_USER_DATA,
            {CONF_HOST: "host_b", CONF_SSL: True},
            {CONF_HOST: "host_b", CONF_PORT: 1234, CONF_SSL: True},
        ),
        (
            {
                CONF_HOST: "fake_host",
                CONF_PORT: 49000,
                CONF_PASSWORD: "fake_pass",
                CONF_USERNAME: "fake_user",
                CONF_SSL: False,
            },
            {CONF_HOST: "host_b", CONF_SSL: False},
            {CONF_HOST: "host_b", CONF_PORT: 49000, CONF_SSL: False},
        ),
        (
            {
                CONF_HOST: "fake_host",
                CONF_PORT: 49000,
                CONF_PASSWORD: "fake_pass",
                CONF_USERNAME: "fake_user",
                CONF_SSL: False,
            },
            {CONF_HOST: "host_b", CONF_SSL: True},
            {CONF_HOST: "host_b", CONF_PORT: 49443, CONF_SSL: True},
        ),
    ],
)
async def test_reconfigure_successful(
    hass: HomeAssistant,
    fc_class_mock,
    initial_config: dict,
    user_input: dict,
    expected_config: dict,
) -> None:
    """Test starting a reconfigure flow."""

    mock_config = MockConfigEntry(domain=DOMAIN, data=initial_config)
    mock_config.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.fritz.config_flow.FritzConnection",
            side_effect=fc_class_mock,
        ),
        patch(
            "homeassistant.components.fritz.coordinator.FritzBoxTools._update_device_info",
            return_value=MOCK_FIRMWARE_INFO,
        ),
        patch(
            "homeassistant.components.fritz.async_setup_entry",
        ) as mock_setup_entry,
        patch(
            "requests.get",
        ) as mock_request_get,
        patch(
            "requests.post",
        ) as mock_request_post,
    ):
        mock_request_get.return_value.status_code = 200
        mock_request_get.return_value.content = MOCK_REQUEST
        mock_request_post.return_value.status_code = 200
        mock_request_post.return_value.text = MOCK_REQUEST

        result = await mock_config.start_reconfigure_flow(hass)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reconfigure"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        assert mock_config.data == {
            **expected_config,
            CONF_USERNAME: "fake_user",
            CONF_PASSWORD: "fake_pass",
        }

    assert mock_setup_entry.called


async def test_reconfigure_not_successful(
    hass: HomeAssistant,
    fc_class_mock,
) -> None:
    """Test starting a reconfigure flow but no connection found."""

    mock_config = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    mock_config.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.fritz.config_flow.FritzConnection",
            side_effect=[FritzConnectionException, fc_class_mock],
        ),
        patch(
            "homeassistant.components.fritz.coordinator.FritzBoxTools._update_device_info",
            return_value=MOCK_FIRMWARE_INFO,
        ),
        patch(
            "homeassistant.components.fritz.async_setup_entry",
        ),
        patch(
            "requests.get",
        ) as mock_request_get,
        patch(
            "requests.post",
        ) as mock_request_post,
    ):
        mock_request_get.return_value.status_code = 200
        mock_request_get.return_value.content = MOCK_REQUEST
        mock_request_post.return_value.status_code = 200
        mock_request_post.return_value.text = MOCK_REQUEST

        result = await mock_config.start_reconfigure_flow(hass)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reconfigure"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "fake_host",
                CONF_SSL: False,
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reconfigure"
        assert result["errors"]["base"] == ERROR_CANNOT_CONNECT

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "fake_host",
                CONF_SSL: False,
            },
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        assert mock_config.data == {
            CONF_HOST: "fake_host",
            CONF_PASSWORD: "fake_pass",
            CONF_USERNAME: "fake_user",
            CONF_PORT: 1234,
            CONF_SSL: False,
        }


async def test_ssdp_already_configured(hass: HomeAssistant, fc_class_mock) -> None:
    """Test starting a flow from discovery with an already configured device."""

    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_DATA,
        unique_id=MOCK_FRITZ_SSDP_DEVICE_UUID,
    )
    mock_config.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.fritz.config_flow.FritzConnection",
            side_effect=fc_class_mock,
        ),
        patch(
            "homeassistant.components.fritz.config_flow.socket.gethostbyname",
            return_value=MOCK_IPS["fritz.box"],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_ssdp_already_configured_keeps_unrelated_unique_id(
    hass: HomeAssistant, fc_class_mock
) -> None:
    """Test SSDP keeps unrelated unique_id for the same host."""

    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_DATA,
        unique_id=MOCK_FRITZ_OTHER_DEVICE_UUID,
    )
    mock_config.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.fritz.config_flow.FritzConnection",
            side_effect=fc_class_mock,
        ),
        patch(
            "homeassistant.components.fritz.config_flow.socket.gethostbyname",
            return_value=MOCK_IPS["fritz.box"],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"
        assert mock_config.unique_id == MOCK_FRITZ_OTHER_DEVICE_UUID


async def test_ssdp_already_configured_migrates_missing_unique_id(
    hass: HomeAssistant, fc_class_mock
) -> None:
    """Test SSDP sets unique_id when the entry has none."""

    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_DATA,
        unique_id=None,
    )
    mock_config.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.fritz.config_flow.FritzConnection",
            side_effect=fc_class_mock,
        ),
        patch(
            "homeassistant.components.fritz.config_flow.socket.gethostbyname",
            return_value=MOCK_IPS["fritz.box"],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"
        assert mock_config.unique_id == MOCK_FRITZ_SSDP_DEVICE_UUID


async def test_ssdp_uuid_from_usn_when_udn_missing(
    hass: HomeAssistant, fc_class_mock
) -> None:
    """Test SSDP reads UUID from USN if UPnP UDN is absent."""
    mock_ssdp = dataclasses.replace(
        MOCK_SSDP_DATA,
        ssdp_usn=MOCK_FRITZ_SSDP_USN,
        upnp={ATTR_UPNP_FRIENDLY_NAME: "fake_name"},
    )

    with (
        patch(
            "homeassistant.components.fritz.config_flow.FritzConnection",
            side_effect=fc_class_mock,
        ),
        patch(
            "homeassistant.components.fritz.config_flow.socket.gethostbyname",
            return_value=MOCK_IPS["fritz.box"],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=mock_ssdp
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"
        assert _flow_unique_id(hass, result["flow_id"]) == MOCK_FRITZ_SSDP_DEVICE_UUID


async def test_ssdp_invalid_udn_uses_usn_uuid(
    hass: HomeAssistant, fc_class_mock
) -> None:
    """Test invalid UPnP UDN falls back to SSDP USN UUID."""
    mock_ssdp = dataclasses.replace(
        MOCK_SSDP_DATA,
        ssdp_usn=MOCK_FRITZ_SSDP_USN,
        upnp={
            ATTR_UPNP_FRIENDLY_NAME: "fake_name",
            ATTR_UPNP_UDN: "uuid:not-a-uuid",
        },
    )

    with (
        patch(
            "homeassistant.components.fritz.config_flow.FritzConnection",
            side_effect=fc_class_mock,
        ),
        patch(
            "homeassistant.components.fritz.config_flow.socket.gethostbyname",
            return_value=MOCK_IPS["fritz.box"],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=mock_ssdp
        )
        assert result["type"] is FlowResultType.FORM
        assert _flow_unique_id(hass, result["flow_id"]) == MOCK_FRITZ_SSDP_DEVICE_UUID


async def test_ssdp_host_unique_id_when_uuid_missing(
    hass: HomeAssistant, fc_class_mock
) -> None:
    """Test SSDP uses host as unique_id without UDN or USN UUID."""
    mock_ssdp = dataclasses.replace(
        MOCK_SSDP_DATA,
        ssdp_usn="mock_usn",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "fake_name"},
    )

    with (
        patch(
            "homeassistant.components.fritz.config_flow.FritzConnection",
            side_effect=fc_class_mock,
        ),
        patch(
            "homeassistant.components.fritz.config_flow.socket.gethostbyname",
            return_value=MOCK_IPS["fritz.box"],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=mock_ssdp
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"
        assert _flow_unique_id(hass, result["flow_id"]) == MOCK_IPS["fritz.box"]


async def test_ssdp_host_unique_id_when_uuid_invalid(
    hass: HomeAssistant, fc_class_mock
) -> None:
    """Test SSDP falls back to host when UDN and USN are not valid UUIDs."""
    mock_ssdp = dataclasses.replace(
        MOCK_SSDP_DATA,
        ssdp_usn="uuid:not-a-uuid::upnp:rootdevice",
        upnp={
            ATTR_UPNP_FRIENDLY_NAME: "fake_name",
            ATTR_UPNP_UDN: "uuid:not-a-uuid",
        },
    )

    with (
        patch(
            "homeassistant.components.fritz.config_flow.FritzConnection",
            side_effect=fc_class_mock,
        ),
        patch(
            "homeassistant.components.fritz.config_flow.socket.gethostbyname",
            return_value=MOCK_IPS["fritz.box"],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=mock_ssdp
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"
        assert _flow_unique_id(hass, result["flow_id"]) == MOCK_IPS["fritz.box"]


async def test_ssdp_migrate_discovered_host_unique_id_to_uuid(
    hass: HomeAssistant, fc_class_mock
) -> None:
    """Test SSDP migrates unique_id from discovered host IP to device UUID."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_DATA,
        unique_id=MOCK_IPS["fritz.box"],
    )
    mock_config.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.fritz.config_flow.FritzConnection",
            side_effect=fc_class_mock,
        ),
        patch(
            "homeassistant.components.fritz.config_flow.socket.gethostbyname",
            return_value=MOCK_IPS["fritz.box"],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"
        assert mock_config.unique_id == MOCK_FRITZ_SSDP_DEVICE_UUID


async def test_ssdp_without_uuid_keeps_host_unique_id(
    hass: HomeAssistant, fc_class_mock
) -> None:
    """Test SSDP does not migrate when discovery provides no device UUID."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_DATA,
        unique_id=MOCK_IPS["fritz.box"],
    )
    mock_config.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.fritz.config_flow.FritzConnection",
            side_effect=fc_class_mock,
        ),
        patch(
            "homeassistant.components.fritz.config_flow.socket.gethostbyname",
            return_value=MOCK_IPS["fritz.box"],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA_NO_UDN
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"
        assert mock_config.unique_id == MOCK_IPS["fritz.box"]


async def test_ssdp_migrate_hostname_unique_id_when_ip_discovered(
    hass: HomeAssistant, fc_class_mock
) -> None:
    """Test SSDP migrates hostname unique_id when discovery reports the IP."""
    host_data = {**MOCK_USER_DATA, CONF_HOST: "fritz.box"}
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data=host_data,
        unique_id="fritz.box",
    )
    mock_config.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.fritz.config_flow.FritzConnection",
            side_effect=fc_class_mock,
        ),
        patch(
            "homeassistant.components.fritz.config_flow.socket.gethostbyname",
            return_value=MOCK_IPS["fritz.box"],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"
        assert mock_config.unique_id == MOCK_FRITZ_SSDP_DEVICE_UUID


async def test_ssdp_migrate_config_host_unique_id_to_uuid(
    hass: HomeAssistant, fc_class_mock
) -> None:
    """Test SSDP migrates unique_id from CONF_HOST to device UUID."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_DATA,
        unique_id=MOCK_USER_DATA[CONF_HOST],
    )
    mock_config.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.fritz.config_flow.FritzConnection",
            side_effect=fc_class_mock,
        ),
        patch(
            "homeassistant.components.fritz.config_flow.socket.gethostbyname",
            return_value=MOCK_IPS["fritz.box"],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"
        assert mock_config.unique_id == MOCK_FRITZ_SSDP_DEVICE_UUID


async def test_ssdp_already_in_progress_host(
    hass: HomeAssistant, fc_class_mock
) -> None:
    """Test starting a flow from discovery twice."""
    with (
        patch(
            "homeassistant.components.fritz.config_flow.FritzConnection",
            side_effect=fc_class_mock,
        ),
        patch(
            "homeassistant.components.fritz.config_flow.socket.gethostbyname",
            return_value=MOCK_IPS["fritz.box"],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA_NO_UDN
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_in_progress"


async def test_ssdp(hass: HomeAssistant, fc_class_mock) -> None:
    """Test starting a flow from discovery."""
    with (
        patch(
            "homeassistant.components.fritz.config_flow.FritzConnection",
            side_effect=fc_class_mock,
        ),
        patch(
            "homeassistant.components.fritz.coordinator.FritzBoxTools._update_device_info",
            return_value=MOCK_FIRMWARE_INFO,
        ),
        patch(
            "homeassistant.components.fritz.config_flow.socket.gethostbyname",
            return_value=MOCK_IPS["fritz.box"],
        ),
        patch("homeassistant.components.fritz.async_setup_entry") as mock_setup_entry,
        patch("requests.get") as mock_request_get,
        patch("requests.post") as mock_request_post,
    ):
        mock_request_get.return_value.status_code = 200
        mock_request_get.return_value.content = MOCK_REQUEST
        mock_request_post.return_value.status_code = 200
        mock_request_post.return_value.text = MOCK_REQUEST

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "fake_user",
                CONF_PASSWORD: "fake_pass",
            },
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_HOST] == MOCK_IPS["fritz.box"]
        assert result["data"][CONF_PASSWORD] == "fake_pass"
        assert result["data"][CONF_USERNAME] == "fake_user"

    assert mock_setup_entry.called


async def test_ssdp_exception(hass: HomeAssistant) -> None:
    """Test starting a flow from discovery but no device found."""
    with (
        patch(
            "homeassistant.components.fritz.config_flow.FritzConnection",
            side_effect=FritzConnectionException,
        ),
        patch(
            "homeassistant.components.fritz.config_flow.socket.gethostbyname",
            return_value=MOCK_IPS["fritz.box"],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_SSDP}, data=MOCK_SSDP_DATA
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "fake_user",
                CONF_PASSWORD: "fake_pass",
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"


async def test_options_flow(hass: HomeAssistant, fc_class_mock) -> None:
    """Test options flow."""

    mock_config = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    mock_config.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_CONSIDER_HOME: 37,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_OLD_DISCOVERY: False,
        CONF_CONSIDER_HOME: 37,
        CONF_FEATURE_DEVICE_TRACKING: True,
    }


async def test_ssdp_aborts_when_host_missing(hass: HomeAssistant) -> None:
    """Test SSDP aborts when no host can be resolved."""
    discovery = SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="mock_st",
        upnp={
            ATTR_UPNP_FRIENDLY_NAME: "fake_name",
            ATTR_UPNP_MODEL_NAME: "fake_model",
        },
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=discovery
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_host"


def test_host_from_ssdp_location_header() -> None:
    """Test host is read from SSDP headers when location is missing."""
    discovery = SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="mock_st",
        ssdp_location=None,
        ssdp_headers={"location": f"https://{MOCK_IPS['fritz.box']}:12345/test"},
        upnp={ATTR_UPNP_FRIENDLY_NAME: "fake_name"},
    )
    assert _host_from_ssdp(discovery) == MOCK_IPS["fritz.box"]


async def test_ssdp_ipv6_link_local(hass: HomeAssistant) -> None:
    """Test ignoring ipv6-link-local while ssdp discovery."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="https://[fe80::1ff:fe23:4567:890a]:12345/test",
            upnp={
                ATTR_UPNP_FRIENDLY_NAME: "fake_name",
                ATTR_UPNP_UDN: MOCK_FRITZ_SSDP_UDN,
            },
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "ignore_ip6_link_local"


async def test_upnp_not_enabled(hass: HomeAssistant) -> None:
    """Test if UPNP service is enabled on the router."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Disable UPnP
    services = deepcopy(MOCK_FB_SERVICES)
    services["X_AVM-DE_UPnP1"]["GetInfo"]["NewEnable"] = False

    with patch(
        "homeassistant.components.fritz.config_flow.FritzConnection",
        return_value=FritzConnectionMock(services),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_INPUT_SIMPLE
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == ERROR_UPNP_NOT_CONFIGURED

    # Enable UPnP
    services["X_AVM-DE_UPnP1"]["GetInfo"]["NewEnable"] = True

    with (
        patch(
            "homeassistant.components.fritz.config_flow.FritzConnection",
            return_value=FritzConnectionMock(services),
        ),
        patch(
            "homeassistant.components.fritz.config_flow.socket.gethostbyname",
            return_value=MOCK_IPS["fritz.box"],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_INPUT_SIMPLE
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_HOST] == "fake_host"
        assert result["data"][CONF_PASSWORD] == "fake_pass"
        assert result["data"][CONF_USERNAME] == "fake_user"
        assert result["data"][CONF_PORT] == 49000
        assert result["data"][CONF_SSL] is False
