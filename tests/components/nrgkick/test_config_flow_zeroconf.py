"""Tests for the NRGkick config flow (zeroconf)."""

from __future__ import annotations

from ipaddress import ip_address
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.nrgkick.api import (
    NRGkickApiClientApiDisabledError,
    NRGkickApiClientAuthenticationError,
    NRGkickApiClientCommunicationError,
    NRGkickApiClientError,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import create_mock_config_entry


async def test_zeroconf_discovery(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test zeroconf discovery flow (auth required)."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="nrgkick.local.",
        name="NRGkick Test._nrgkick._tcp.local.",
        port=80,
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "model_type": "NRGkick Gen2",
            "json_api_enabled": "1",
            "json_api_version": "v1",
        },
        type="_nrgkick._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"] == {
        "name": "NRGkick Test",
        "device_ip": "192.168.1.100",
    }

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    with (
        patch(
            "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
            return_value=mock_nrgkick_api,
        ),
        patch(
            "homeassistant.components.nrgkick.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "zeroconf_auth"

    mock_nrgkick_api.test_connection.side_effect = None

    with (
        patch(
            "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
            return_value=mock_nrgkick_api,
        ),
        patch(
            "homeassistant.components.nrgkick.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_USERNAME: "test_user", CONF_PASSWORD: "test_pass"},
        )
        await hass.async_block_till_done()

    assert result3["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result3["title"] == "NRGkick Test"
    assert result3["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_pass",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_discovery_without_credentials(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test zeroconf discovery without credentials."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="nrgkick.local.",
        name="NRGkick Test._nrgkick._tcp.local.",
        port=80,
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "model_type": "NRGkick Gen2",
            "json_api_enabled": "1",
        },
        type="_nrgkick._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    with (
        patch(
            "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
            return_value=mock_nrgkick_api,
        ),
        patch(
            "homeassistant.components.nrgkick.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["data"] == {CONF_HOST: "192.168.1.100"}


async def test_zeroconf_discovery_invalid_auth(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test zeroconf auth step invalid_auth on wrong credentials."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="nrgkick.local.",
        name="NRGkick Test._nrgkick._tcp.local.",
        port=80,
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "json_api_enabled": "1",
        },
        type="_nrgkick._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "zeroconf_auth"

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_USERNAME: "wrong_user", CONF_PASSWORD: "wrong_pass"},
        )

    assert result3["type"] == data_entry_flow.FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_auth"}


async def test_zeroconf_discovery_unknown_exception(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test zeroconf confirm step handles unexpected exception."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="nrgkick.local.",
        name="NRGkick Test._nrgkick._tcp.local.",
        port=80,
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "json_api_enabled": "1",
        },
        type="_nrgkick._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_zeroconf_already_configured(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test zeroconf discovery when device is already configured."""
    entry = create_mock_config_entry(
        domain="nrgkick",
        title="NRGkick Test",
        data={CONF_HOST: "192.168.1.200"},
        entry_id="test_entry",
        unique_id="TEST123456",
    )
    entry.add_to_hass(hass)

    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="nrgkick.local.",
        name="NRGkick Test._nrgkick._tcp.local.",
        port=80,
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "json_api_enabled": "1",
        },
        type="_nrgkick._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.168.1.100"


async def test_zeroconf_json_api_disabled(hass: HomeAssistant) -> None:
    """Test zeroconf discovery when JSON API is disabled."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="nrgkick.local.",
        name="NRGkick Test._nrgkick._tcp.local.",
        port=80,
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "json_api_enabled": "0",
        },
        type="_nrgkick._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "zeroconf_enable_json_api"
    assert result["description_placeholders"] == {
        "name": "NRGkick Test",
        "device_ip": "192.168.1.100",
    }


async def test_zeroconf_json_api_disabled_then_enabled(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test zeroconf discovery guides user and completes once enabled."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="nrgkick.local.",
        name="NRGkick Test._nrgkick._tcp.local.",
        port=80,
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "json_api_enabled": "0",
        },
        type="_nrgkick._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "zeroconf_enable_json_api"

    with (
        patch(
            "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
            return_value=mock_nrgkick_api,
        ),
        patch(
            "homeassistant.components.nrgkick.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "NRGkick Test"
    assert result2["data"] == {CONF_HOST: "192.168.1.100"}


async def test_zeroconf_json_api_disabled_auth_required_then_success(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test JSON API disabled flow that requires authentication afterwards."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="nrgkick.local.",
        name="NRGkick Test._nrgkick._tcp.local.",
        port=80,
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "json_api_enabled": "0",
        },
        type="_nrgkick._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "zeroconf_enable_json_api"

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "zeroconf_enable_json_api_auth"

    mock_nrgkick_api.test_connection.side_effect = None

    with (
        patch(
            "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
            return_value=mock_nrgkick_api,
        ),
        patch("homeassistant.components.nrgkick.async_setup_entry", return_value=True),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )
        await hass.async_block_till_done()

    assert result3["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result3["data"] == {
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
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="nrgkick.local.",
        name="NRGkick Test._nrgkick._tcp.local.",
        port=80,
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "json_api_enabled": "0",
        },
        type="_nrgkick._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["step_id"] == "zeroconf_enable_json_api"

    mock_nrgkick_api.test_connection.side_effect = side_effect

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": expected}


async def test_zeroconf_json_api_disabled_no_serial_number(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test JSON API disabled flow reports missing serial number."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="nrgkick.local.",
        name="NRGkick Test._nrgkick._tcp.local.",
        port=80,
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "json_api_enabled": "0",
        },
        type="_nrgkick._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["step_id"] == "zeroconf_enable_json_api"

    mock_nrgkick_api.test_connection.side_effect = None
    mock_nrgkick_api.get_info.return_value = {
        "general": {"device_name": "NRGkick Test"}
    }

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "no_serial_number"}


async def test_zeroconf_json_api_still_disabled_reports_error(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test JSON API disabled flow reports json_api_disabled when still off."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="nrgkick.local.",
        name="NRGkick Test._nrgkick._tcp.local.",
        port=80,
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "json_api_enabled": "0",
        },
        type="_nrgkick._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["step_id"] == "zeroconf_enable_json_api"

    mock_nrgkick_api.test_connection.side_effect = None
    mock_nrgkick_api.get_info.side_effect = NRGkickApiClientApiDisabledError

    with patch(
        "custom_components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "zeroconf_enable_json_api"
    assert result2["errors"] == {"base": "json_api_disabled"}


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    [
        (NRGkickApiClientAuthenticationError, "invalid_auth"),
        (NRGkickApiClientCommunicationError, "cannot_connect"),
        (NRGkickApiClientError, "unknown"),
    ],
)
async def test_zeroconf_enable_json_api_auth_errors(
    hass: HomeAssistant, mock_nrgkick_api, side_effect: type[Exception], expected: str
) -> None:
    """Test JSON API enable auth step reports errors."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="nrgkick.local.",
        name="NRGkick Test._nrgkick._tcp.local.",
        port=80,
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "json_api_enabled": "0",
        },
        type="_nrgkick._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result2["step_id"] == "zeroconf_enable_json_api_auth"

    mock_nrgkick_api.test_connection.side_effect = side_effect

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    assert result3["type"] == data_entry_flow.FlowResultType.FORM
    assert result3["errors"] == {"base": expected}


async def test_zeroconf_no_serial_number(hass: HomeAssistant) -> None:
    """Test zeroconf discovery without serial number."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="nrgkick.local.",
        name="NRGkick Test._nrgkick._tcp.local.",
        port=80,
        properties={
            "device_name": "NRGkick Test",
            "json_api_enabled": "1",
        },
        type="_nrgkick._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "no_serial_number"


async def test_zeroconf_cannot_connect(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test zeroconf discovery with connection error."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="nrgkick.local.",
        name="NRGkick Test._nrgkick._tcp.local.",
        port=80,
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "json_api_enabled": "1",
        },
        type="_nrgkick._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientCommunicationError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_zeroconf_confirm_no_serial_number_from_api(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test zeroconf confirm handles missing serial from API response."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="nrgkick.local.",
        name="NRGkick Test._nrgkick._tcp.local.",
        port=80,
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "json_api_enabled": "1",
        },
        type="_nrgkick._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    mock_nrgkick_api.get_info.return_value = {
        "general": {"device_name": "NRGkick Test"}
    }

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "no_serial_number"}


async def test_zeroconf_auth_reports_cannot_connect(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test zeroconf auth step reports cannot_connect."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="nrgkick.local.",
        name="NRGkick Test._nrgkick._tcp.local.",
        port=80,
        properties={
            "serial_number": "TEST123456",
            "device_name": "NRGkick Test",
            "json_api_enabled": "1",
        },
        type="_nrgkick._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result2["step_id"] == "zeroconf_auth"

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientCommunicationError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    assert result3["type"] == data_entry_flow.FlowResultType.FORM
    assert result3["errors"] == {"base": "cannot_connect"}


async def test_zeroconf_fallback_to_model_type(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test zeroconf discovery uses model_type when device_name is missing."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="nrgkick.local.",
        name="NRGkick Gen2 SIM._nrgkick._tcp.local.",
        port=80,
        properties={
            "serial_number": "TEST123456",
            "model_type": "NRGkick Gen2 SIM",
            "json_api_enabled": "1",
        },
        type="_nrgkick._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["description_placeholders"] == {
        "name": "NRGkick Gen2 SIM",
        "device_ip": "192.168.1.100",
    }


async def test_zeroconf_fallback_to_default_name(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test zeroconf when device_name and model_type are missing."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="nrgkick.local.",
        name="Unknown Device._nrgkick._tcp.local.",
        port=80,
        properties={
            "serial_number": "TEST123456",
            "json_api_enabled": "1",
        },
        type="_nrgkick._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    placeholders = result.get("description_placeholders")
    assert placeholders is not None
    assert placeholders["name"] == "NRGkick"
    assert placeholders["device_ip"] == "192.168.1.100"
