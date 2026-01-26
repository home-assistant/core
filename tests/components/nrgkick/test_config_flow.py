"""Tests for the NRGkick config flow."""

from __future__ import annotations

from ipaddress import ip_address

import pytest

from homeassistant.components.nrgkick.api import (
    NRGkickApiClientApiDisabledError,
    NRGkickApiClientAuthenticationError,
    NRGkickApiClientCommunicationError,
    NRGkickApiClientError,
)
from homeassistant.components.nrgkick.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import create_mock_config_entry


def _make_discovery_info(
    *,
    properties: dict[str, str],
    ip: str = "192.168.1.100",
    name: str = "NRGkick Test._nrgkick._tcp.local.",
    hostname: str = "nrgkick.local.",
    port: int = 80,
    type_: str = "_nrgkick._tcp.local.",
) -> ZeroconfServiceInfo:
    """Create zeroconf discovery info for tests."""
    ip_addr = ip_address(ip)
    return ZeroconfServiceInfo(
        ip_address=ip_addr,
        ip_addresses=[ip_addr],
        hostname=hostname,
        name=name,
        port=port,
        properties=properties,
        type=type_,
    )


TEST_CONNECTION_ERRORS: list[tuple[type[Exception], str]] = [
    (NRGkickApiClientCommunicationError, "cannot_connect"),
    (NRGkickApiClientError, "unknown"),
    (NRGkickApiClientApiDisabledError, "json_api_disabled"),
]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_without_credentials(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test we can set up successfully without credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_HOST: "192.168.1.100"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NRGkick Test"
    assert result["data"] == {CONF_HOST: "192.168.1.100"}


async def test_form(hass: HomeAssistant, mock_nrgkick_api, mock_setup_entry) -> None:
    """Test we can setup when authentication is required."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_HOST: "192.168.1.100"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_auth"

    mock_nrgkick_api.test_connection.side_effect = None

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_pass",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NRGkick Test"
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_pass",
    }
    mock_setup_entry.assert_called_once()


async def test_form_invalid_host_input(hass: HomeAssistant) -> None:
    """Test we handle invalid host input during normalization."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_HOST: "http://"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_fallback_title_when_device_name_missing(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test we fall back to a default title when device name is missing."""
    mock_nrgkick_api.get_info.return_value = {"general": {"serial_number": "ABC"}}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_HOST: "192.168.1.100"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NRGkick"
    assert result["data"] == {CONF_HOST: "192.168.1.100"}


async def test_form_invalid_response_when_serial_missing(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test we handle invalid device info response."""
    mock_nrgkick_api.get_info.return_value = {"general": {"device_name": "NRGkick"}}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_response"}


@pytest.mark.parametrize(
    "scenario",
    [
        {
            "name": "cannot_connect",
            "steps": [
                {
                    "side_effect": NRGkickApiClientCommunicationError,
                    "user_input": {CONF_HOST: "192.168.1.100"},
                    "errors": {"base": "cannot_connect"},
                },
            ],
            "final_user_input": {CONF_HOST: "192.168.1.100"},
            "final_data": {CONF_HOST: "192.168.1.100"},
        },
        {
            "name": "invalid_auth",
            "steps": [
                {
                    "side_effect": NRGkickApiClientAuthenticationError,
                    "user_input": {CONF_HOST: "192.168.1.100"},
                    "step_id": "user_auth",
                },
                {
                    "side_effect": NRGkickApiClientAuthenticationError,
                    "user_input": {
                        CONF_USERNAME: "test-username",
                        CONF_PASSWORD: "test-password",
                    },
                    "errors": {"base": "invalid_auth"},
                },
            ],
            "final_user_input": {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
            "final_data": {
                CONF_HOST: "192.168.1.100",
                CONF_USERNAME: "user",
                CONF_PASSWORD: "pass",
            },
        },
    ],
    ids=lambda scenario: scenario["name"],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_error_then_recovers_to_create_entry(
    hass: HomeAssistant, mock_nrgkick_api, scenario: dict
) -> None:
    """Test errors are handled and the flow can recover to CREATE_ENTRY."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    flow_id = result["flow_id"]
    for step in scenario["steps"]:
        mock_nrgkick_api.test_connection.side_effect = step.get("side_effect")

        result = await hass.config_entries.flow.async_configure(
            flow_id,
            step["user_input"],
        )

        assert result["type"] is FlowResultType.FORM
        if step_id := step.get("step_id"):
            assert result["step_id"] == step_id
        if errors := step.get("errors"):
            assert result["errors"] == errors

        flow_id = result["flow_id"]

    mock_nrgkick_api.test_connection.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        flow_id,
        scenario["final_user_input"],
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == scenario["final_data"]


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    TEST_CONNECTION_ERRORS,
    ids=["cannot_connect", "unknown", "json_api_disabled"],
)
async def test_user_auth_step_errors(
    hass: HomeAssistant,
    mock_nrgkick_api,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test user auth step errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_auth"

    mock_nrgkick_api.test_connection.side_effect = side_effect

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (NRGkickApiClientError, "unknown"),
        (NRGkickApiClientApiDisabledError, "json_api_disabled"),
    ],
    ids=["unknown", "json_api_disabled"],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_nrgkick_api,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test we handle user step errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_nrgkick_api.test_connection.side_effect = side_effect

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


async def test_form_already_configured(
    hass: HomeAssistant, mock_config_entry, mock_nrgkick_api
) -> None:
    """Test we handle already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_HOST: "192.168.1.100"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_discovery(
    hass: HomeAssistant, mock_nrgkick_api, mock_setup_entry
) -> None:
    """Test zeroconf discovery flow (auth required)."""
    discovery_info = _make_discovery_info(
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "model_type": "NRGkick Gen2",
            "json_api_enabled": "1",
            "json_api_version": "v1",
        }
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_auth"
    assert result["description_placeholders"] == {"device_ip": "192.168.1.100"}

    mock_nrgkick_api.test_connection.side_effect = None

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_USERNAME: "test_user", CONF_PASSWORD: "test_pass"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NRGkick Test"
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_pass",
    }
    mock_setup_entry.assert_called_once()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_discovery_without_credentials(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test zeroconf discovery without credentials."""
    discovery_info = _make_discovery_info(
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "model_type": "NRGkick Gen2",
            "json_api_enabled": "1",
        }
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(flow_id, {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "192.168.1.100"}


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    TEST_CONNECTION_ERRORS,
    ids=["cannot_connect", "unknown", "json_api_disabled"],
)
async def test_zeroconf_confirm_errors(
    hass: HomeAssistant,
    mock_nrgkick_api,
    side_effect: type[Exception],
    expected: str,
) -> None:
    """Test zeroconf confirm step reports errors."""
    discovery_info = _make_discovery_info(
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "json_api_enabled": "1",
        }
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["step_id"] == "zeroconf_confirm"

    mock_nrgkick_api.test_connection.side_effect = side_effect

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(flow_id, {})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}


async def test_zeroconf_already_configured(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test zeroconf discovery when device is already configured."""
    entry = create_mock_config_entry(
        domain=DOMAIN,
        title="NRGkick Test",
        data={CONF_HOST: "192.168.1.200"},
        entry_id="test_entry",
        unique_id="TEST123456",
    )
    entry.add_to_hass(hass)

    discovery_info = _make_discovery_info(
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "json_api_enabled": "1",
        }
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.168.1.100"


async def test_zeroconf_json_api_disabled(hass: HomeAssistant) -> None:
    """Test zeroconf discovery when JSON API is disabled."""
    discovery_info = _make_discovery_info(
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "json_api_enabled": "0",
        }
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_enable_json_api"
    assert result["description_placeholders"] == {
        "name": "NRGkick Test",
        "device_ip": "192.168.1.100",
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_json_api_disabled_then_enabled(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test zeroconf discovery guides user and completes once enabled."""
    discovery_info = _make_discovery_info(
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "json_api_enabled": "0",
        }
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_enable_json_api"

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(flow_id, {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NRGkick Test"
    assert result["data"] == {CONF_HOST: "192.168.1.100"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_json_api_disabled_auth_required_then_success(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test JSON API disabled flow that requires authentication afterwards."""
    discovery_info = _make_discovery_info(
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "json_api_enabled": "0",
        }
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_enable_json_api"

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(flow_id, {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user_auth"

    mock_nrgkick_api.test_connection.side_effect = None

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_USERNAME: "user",
        CONF_PASSWORD: "pass",
    }


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    [
        (NRGkickApiClientCommunicationError, "cannot_connect"),
        (NRGkickApiClientError, "unknown"),
    ],
)
async def test_zeroconf_json_api_disabled_errors(
    hass: HomeAssistant, mock_nrgkick_api, side_effect: type[Exception], expected: str
) -> None:
    """Test JSON API disabled flow reports connection and unknown errors."""
    discovery_info = _make_discovery_info(
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "json_api_enabled": "0",
        }
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["step_id"] == "zeroconf_enable_json_api"

    mock_nrgkick_api.test_connection.side_effect = side_effect

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(flow_id, {})

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}


async def test_zeroconf_json_api_still_disabled_reports_error(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test JSON API disabled flow reports json_api_disabled when still off."""
    discovery_info = _make_discovery_info(
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "json_api_enabled": "0",
        }
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["step_id"] == "zeroconf_enable_json_api"

    mock_nrgkick_api.test_connection.side_effect = None
    mock_nrgkick_api.get_info.side_effect = NRGkickApiClientApiDisabledError

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(flow_id, {})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_enable_json_api"
    assert result["errors"] == {"base": "json_api_disabled"}


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    [
        (NRGkickApiClientApiDisabledError, "json_api_disabled"),
        (NRGkickApiClientAuthenticationError, "invalid_auth"),
        (NRGkickApiClientCommunicationError, "cannot_connect"),
        (NRGkickApiClientError, "unknown"),
    ],
)
async def test_zeroconf_enable_json_api_auth_errors(
    hass: HomeAssistant, mock_nrgkick_api, side_effect: type[Exception], expected: str
) -> None:
    """Test JSON API enable auth step reports errors."""
    discovery_info = _make_discovery_info(
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "json_api_enabled": "0",
        }
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(flow_id, {})

    assert result["step_id"] == "user_auth"

    mock_nrgkick_api.test_connection.side_effect = side_effect

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}


@pytest.mark.parametrize(
    ("second_side_effect", "expected"),
    [
        (NRGkickApiClientAuthenticationError, "invalid_auth"),
        (NRGkickApiClientCommunicationError, "cannot_connect"),
        (NRGkickApiClientApiDisabledError, "json_api_disabled"),
        (NRGkickApiClientError, "unknown"),
    ],
    ids=["invalid_auth", "cannot_connect", "json_api_disabled", "unknown"],
)
async def test_zeroconf_auth_errors(
    hass: HomeAssistant,
    mock_nrgkick_api,
    second_side_effect: type[Exception],
    expected: str,
) -> None:
    """Test zeroconf auth step reports errors."""
    discovery_info = _make_discovery_info(
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "json_api_enabled": "1",
        }
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["step_id"] == "user_auth"

    mock_nrgkick_api.test_connection.side_effect = second_side_effect

    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}


async def test_zeroconf_no_serial_number(hass: HomeAssistant) -> None:
    """Test zeroconf discovery without serial number."""
    discovery_info = _make_discovery_info(
        properties={
            "device_name": "NRGkick Test",
            "json_api_enabled": "1",
        }
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_serial_number"


@pytest.mark.parametrize(
    ("name", "properties", "expected_name"),
    [
        (
            "NRGkick Gen2 SIM._nrgkick._tcp.local.",
            {
                "serial_number": "TEST123456",
                "model_type": "NRGkick Gen2 SIM",
                "json_api_enabled": "1",
            },
            "NRGkick Gen2 SIM",
        ),
        (
            "Unknown Device._nrgkick._tcp.local.",
            {
                "serial_number": "TEST123456",
                "json_api_enabled": "1",
            },
            "NRGkick",
        ),
    ],
    ids=["model_type", "default_name"],
)
async def test_zeroconf_name_fallbacks(
    hass: HomeAssistant,
    mock_nrgkick_api,
    name: str,
    properties: dict[str, str],
    expected_name: str,
) -> None:
    """Test zeroconf discovery uses fallbacks for device name."""
    discovery_info = _make_discovery_info(name=name, properties=properties)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"] == {
        "name": expected_name,
        "device_ip": "192.168.1.100",
    }
