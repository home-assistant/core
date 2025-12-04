"""Test the Kiosker config flow."""

from ipaddress import ip_address
from unittest.mock import Mock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.kiosker.config_flow import CannotConnect, validate_input
from homeassistant.components.kiosker.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry

DISCOVERY_INFO = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.1.39"),
    ip_addresses=[ip_address("192.168.1.39")],
    hostname="kiosker-device.local.",
    name="Kiosker Device._kiosker._tcp.local.",
    port=8081,
    properties={
        "uuid": "A98BE1CE-1234-1234-1234-123456789ABC",
        "app": "Kiosker",
        "version": "1.0.0",
    },
    type="_kiosker._tcp.local.",
)

DISCOVERY_INFO_NO_UUID = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.1.39"),
    ip_addresses=[ip_address("192.168.1.39")],
    hostname="kiosker-device.local.",
    name="Kiosker Device._kiosker._tcp.local.",
    port=8081,
    properties={"app": "Kiosker", "version": "1.0.0"},
    type="_kiosker._tcp.local.",
)


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.kiosker.config_flow.validate_input"
        ) as mock_validate,
        patch(
            "homeassistant.components.kiosker.async_setup_entry", return_value=True
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.kiosker.config_flow.KioskerAPI"
        ) as mock_api_class,
    ):
        mock_status = Mock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_api = Mock()
        mock_api.status.return_value = mock_status
        mock_api_class.return_value = mock_api

        mock_validate.return_value = {"title": "Kiosker A98BE1CE"}

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 8081,
                "api_token": "test-token",
                "ssl": False,
                "ssl_verify": False,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Kiosker A98BE1CE"
    assert result2["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 8081,
        "api_token": "test-token",
        "ssl": False,
        "ssl_verify": False,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_host(hass: HomeAssistant) -> None:
    """Test we handle invalid host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.kiosker.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 8081,
                "api_token": "test-token",
                "ssl": False,
                "ssl_verify": False,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unexpected_exception(hass: HomeAssistant) -> None:
    """Test we handle unexpected exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.kiosker.config_flow.validate_input",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 8081,
                "api_token": "test-token",
                "ssl": False,
                "ssl_verify": False,
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_zeroconf(hass: HomeAssistant) -> None:
    """Test zeroconf discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    # Check description placeholders instead of context
    assert result["description_placeholders"] == {
        "name": "Kiosker (A98BE1CE)",
        "host": "192.168.1.39",
        "port": "8081",
    }


async def test_zeroconf_no_uuid(hass: HomeAssistant) -> None:
    """Test zeroconf discovery without UUID."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=DISCOVERY_INFO_NO_UUID,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    # Check description placeholders instead of context
    assert result["description_placeholders"] == {
        "name": "Kiosker 192.168.1.39",
        "host": "192.168.1.39",
        "port": "8081",
    }


async def test_zeroconf_confirm(hass: HomeAssistant) -> None:
    """Test zeroconf confirmation step shows form for API token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=DISCOVERY_INFO,
    )

    result_confirm = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result_confirm["type"] is FlowResultType.FORM
    assert result_confirm["step_id"] == "zeroconf_confirm"
    # Check that the form includes API token field
    schema_keys = list(result_confirm["data_schema"].schema.keys())
    assert any(key.schema == "api_token" for key in schema_keys)


async def test_zeroconf_discovery_confirm(hass: HomeAssistant) -> None:
    """Test zeroconf discovery confirmation with token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=DISCOVERY_INFO,
    )

    _result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    with (
        patch(
            "homeassistant.components.kiosker.config_flow.validate_input"
        ) as mock_validate,
        patch(
            "homeassistant.components.kiosker.async_setup_entry", return_value=True
        ) as mock_setup_entry,
    ):
        mock_validate.return_value = {"title": "Kiosker Device"}

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_token": "test-token",
                "ssl": False,
                "ssl_verify": False,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Kiosker Device"
    assert result3["data"] == {
        CONF_HOST: "192.168.1.39",
        CONF_PORT: 8081,
        "api_token": "test-token",
        "ssl": False,
        "ssl_verify": False,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_discovery_confirm_cannot_connect(hass: HomeAssistant) -> None:
    """Test zeroconf discovery confirmation with connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=DISCOVERY_INFO,
    )

    _result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    with patch(
        "homeassistant.components.kiosker.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_token": "test-token",
                "ssl": False,
                "ssl_verify": False,
            },
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"api_token": "cannot_connect"}


async def test_abort_if_already_configured(hass: HomeAssistant) -> None:
    """Test we abort if already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100", CONF_PORT: 8081, "api_token": "test_token"},
        unique_id="A98BE1CE-5FE7-4A8D-B2C3-123456789ABC",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.kiosker.config_flow.validate_input"
        ) as mock_validate,
        patch(
            "homeassistant.components.kiosker.config_flow.KioskerAPI"
        ) as mock_api_class,
    ):
        mock_status = Mock()
        mock_status.device_id = "A98BE1CE-5FE7-4A8D-B2C3-123456789ABC"
        mock_api = Mock()
        mock_api.status.return_value = mock_status
        mock_api_class.return_value = mock_api

        mock_validate.return_value = {"title": "Kiosker A98BE1CE"}

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.200",
                CONF_PORT: 8081,
                "api_token": "test-token",
                "ssl": False,
                "ssl_verify": False,
            },
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_zeroconf_abort_if_already_configured(hass: HomeAssistant) -> None:
    """Test we abort zeroconf discovery if already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100", CONF_PORT: 8081, "api_token": "test_token"},
        unique_id="A98BE1CE-1234-1234-1234-123456789ABC",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=DISCOVERY_INFO,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_manual_setup_with_device_id_fallback(hass: HomeAssistant) -> None:
    """Test manual setup falls back to host:port when device_id unavailable."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.kiosker.config_flow.validate_input"
        ) as mock_validate,
        patch("homeassistant.components.kiosker.async_setup_entry", return_value=True),
        patch(
            "homeassistant.components.kiosker.config_flow.KioskerAPI"
        ) as mock_api_class,
    ):
        # Mock API that fails to get status
        mock_api = Mock()
        mock_api.status.side_effect = Exception("Connection failed")
        mock_api_class.return_value = mock_api

        mock_validate.return_value = {"title": "Kiosker 192.168.1.100"}

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_PORT: 8081,
                "api_token": "test-token",
                "ssl": False,
                "ssl_verify": False,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Kiosker 192.168.1.100"


async def test_validate_input_success(
    hass: HomeAssistant,
    mock_kiosker_api: Mock,
    mock_kiosker_api_class: Mock,
) -> None:
    """Test validate_input with successful connection."""

    mock_kiosker_api_class.return_value = mock_kiosker_api

    data = {
        CONF_HOST: "10.0.1.5",
        CONF_PORT: 8081,
        "api_token": "test_token",
        "ssl": False,
        "ssl_verify": False,
    }

    result = await validate_input(hass, data)
    assert result == {"title": "Kiosker A98BE1CE"}


async def test_validate_input_connection_error(
    hass: HomeAssistant,
    mock_kiosker_api: Mock,
    mock_kiosker_api_class: Mock,
) -> None:
    """Test validate_input with connection error."""

    mock_kiosker_api.status.side_effect = Exception("Connection failed")
    mock_kiosker_api_class.return_value = mock_kiosker_api

    data = {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 8081,
        "api_token": "test_token",
        "ssl": False,
        "ssl_verify": False,
    }

    with pytest.raises(CannotConnect):
        await validate_input(hass, data)
