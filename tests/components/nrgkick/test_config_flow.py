"""Tests for the NRGkick config flow."""

from __future__ import annotations

from ipaddress import ip_address
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.nrgkick.api import (
    NRGkickApiClientAuthenticationError,
    NRGkickApiClientCommunicationError,
)
from homeassistant.components.nrgkick.const import CONF_SCAN_INTERVAL
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import create_mock_config_entry


async def test_form(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        "nrgkick", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_USERNAME: "test_user",
                CONF_PASSWORD: "test_pass",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "NRGkick Test"
    assert result2["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_pass",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_without_credentials(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test we can setup without credentials."""
    result = await hass.config_entries.flow.async_init(
        "nrgkick", context={"source": config_entries.SOURCE_USER}
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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.100"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "NRGkick Test"
    assert result2["data"] == {CONF_HOST: "192.168.1.100"}


async def test_form_cannot_connect(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        "nrgkick", context={"source": config_entries.SOURCE_USER}
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientCommunicationError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.100"},
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_invalid_auth(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test we handle invalid auth error."""
    result = await hass.config_entries.flow.async_init(
        "nrgkick", context={"source": config_entries.SOURCE_USER}
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_unknown_exception(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test we handle unknown exception."""
    result = await hass.config_entries.flow.async_init(
        "nrgkick", context={"source": config_entries.SOURCE_USER}
    )

    mock_nrgkick_api.test_connection.side_effect = Exception("Unexpected error")

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.100"},
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_already_configured(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test we handle already configured."""
    entry = create_mock_config_entry(
        domain="nrgkick",
        title="NRGkick Test",
        data={CONF_HOST: "192.168.1.100"},
        entry_id="test_entry",
        unique_id="TEST123456",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        "nrgkick", context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.100"},
        )

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_reauth_flow(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test reauth flow."""
    entry = create_mock_config_entry(
        domain="nrgkick",
        title="NRGkick Test",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "old_user",
            CONF_PASSWORD: "old_pass",
        },
        entry_id="test_entry",
        unique_id="TEST123456",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
        data=entry.data,
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "new_user",
                CONF_PASSWORD: "new_pass",
            },
        )

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data[CONF_USERNAME] == "new_user"
    assert entry.data[CONF_PASSWORD] == "new_pass"


async def test_reauth_flow_cannot_connect(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test reauth flow with connection error."""
    entry = create_mock_config_entry(
        domain="nrgkick",
        title="NRGkick Test",
        data={CONF_HOST: "192.168.1.100"},
        entry_id="test_entry",
        unique_id="TEST123456",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientCommunicationError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "new_user",
                CONF_PASSWORD: "new_pass",
            },
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_options_flow_success(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test a successful options flow."""
    entry = create_mock_config_entry(
        domain="nrgkick",
        title="NRGkick Test",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "old_user",
            CONF_PASSWORD: "old_pass",
        },
        options={CONF_SCAN_INTERVAL: 30},
        entry_id="test_entry",
        unique_id="TEST123456",
    )
    entry.add_to_hass(hass)

    # Set up the entry to register the update listener
    with (
        patch(
            "homeassistant.components.nrgkick.NRGkickAPI",
            return_value=mock_nrgkick_api,
        ),
        patch("homeassistant.config_entries.ConfigEntries.async_reload"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    with (
        patch(
            "homeassistant.components.nrgkick.config_flow.validate_input",
            return_value={"title": "NRGkick Test", "serial": "TEST123456"},
        ),
        patch("homeassistant.config_entries.ConfigEntries.async_reload") as mock_reload,
    ):
        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_SCAN_INTERVAL: 60,
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result2["data"] == {CONF_SCAN_INTERVAL: 60}

        # Wait for config entry to be updated
        await hass.async_block_till_done()

        # Re-fetch the entry from hass to get updated values
        updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
        assert updated_entry is not None
        assert updated_entry.options.get(CONF_SCAN_INTERVAL) == 60
        # The update listener triggers reload automatically (may be called 1-2 times)
        assert len(mock_reload.mock_calls) >= 1
        mock_reload.assert_called_with(entry.entry_id)


async def test_reconfigure_flow(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test reconfigure flow."""
    entry = create_mock_config_entry(
        domain="nrgkick",
        title="NRGkick Test",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "old_user",
            CONF_PASSWORD: "old_pass",
        },
        entry_id="test_entry",
        unique_id="TEST123456",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reconfigure_confirm"

    with (
        patch(
            "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
            return_value=mock_nrgkick_api,
        ),
        patch("homeassistant.components.nrgkick.async_setup_entry", return_value=True),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.200",
                CONF_USERNAME: "new_user",
                CONF_PASSWORD: "new_pass",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"

    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated_entry.data[CONF_HOST] == "192.168.1.200"
    assert updated_entry.data[CONF_USERNAME] == "new_user"
    assert updated_entry.data[CONF_PASSWORD] == "new_pass"


async def test_reconfigure_flow_cannot_connect(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test reconfigure flow with connection error."""
    entry = create_mock_config_entry(
        domain="nrgkick",
        title="NRGkick Test",
        data={CONF_HOST: "192.168.1.100"},
        entry_id="test_entry",
        unique_id="TEST123456",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientCommunicationError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.200",
                CONF_USERNAME: "new_user",
                CONF_PASSWORD: "new_pass",
            },
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_flow_invalid_auth(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test reconfigure flow with invalid auth."""
    entry = create_mock_config_entry(
        domain="nrgkick",
        title="NRGkick Test",
        data={CONF_HOST: "192.168.1.100"},
        entry_id="test_entry",
        unique_id="TEST123456",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.200",
                CONF_USERNAME: "new_user",
                CONF_PASSWORD: "new_pass",
            },
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reconfigure_flow_no_auth_to_auth_required(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test reconfigure flow when moving from no auth to auth required."""
    # Create entry without authentication
    entry = create_mock_config_entry(
        domain="nrgkick",
        title="NRGkick Test",
        data={CONF_HOST: "192.168.1.100"},
        entry_id="test_entry",
        unique_id="TEST123456",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reconfigure_confirm"

    # Simulate device now requires authentication
    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        # User submits without credentials (form should show with defaults)
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
            },
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    # Now provide credentials
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
            {
                CONF_HOST: "192.168.1.100",
                CONF_USERNAME: "user",
                CONF_PASSWORD: "pass",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == data_entry_flow.FlowResultType.ABORT
    assert result3["reason"] == "reconfigure_successful"

    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated_entry.data[CONF_HOST] == "192.168.1.100"
    assert updated_entry.data[CONF_USERNAME] == "user"
    assert updated_entry.data[CONF_PASSWORD] == "pass"


# Zeroconf Discovery Tests


async def test_zeroconf_discovery(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test zeroconf discovery flow."""
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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test_user",
                CONF_PASSWORD: "test_pass",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "NRGkick Test"
    assert result2["data"] == {
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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    # When no credentials provided, they are stored as None in the data
    assert result2["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_USERNAME: None,
        CONF_PASSWORD: None,
    }


async def test_zeroconf_already_configured(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test zeroconf discovery when device is already configured."""
    entry = create_mock_config_entry(
        domain="nrgkick",
        title="NRGkick Test",
        data={CONF_HOST: "192.168.1.200"},  # Different IP
        entry_id="test_entry",
        unique_id="TEST123456",  # Same serial
    )
    entry.add_to_hass(hass)

    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),  # New IP
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="nrgkick.local.",
        name="NRGkick Test._nrgkick._tcp.local.",
        port=80,
        properties={
            "serial_number": "TEST123456",  # Same serial
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
    # Verify IP was updated
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
            "json_api_enabled": "0",  # Disabled
        },
        type="_nrgkick._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "json_api_disabled"


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
            # No serial_number
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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_zeroconf_fallback_to_model_type(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test zeroconf discovery uses model_type when device_name is missing."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100")],
        hostname="nrgkick.local.",
        # Service name includes model in this test
        name="NRGkick Gen2 SIM._nrgkick._tcp.local.",
        port=80,
        properties={
            "serial_number": "TEST123456",
            "model_type": "NRGkick Gen2 SIM",
            "json_api_enabled": "1",
            # No device_name - should fallback to model_type from properties
        },
        type="_nrgkick._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        "nrgkick",
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    # When device_name is not in properties, it falls back to model_type
    assert result["description_placeholders"] == {
        "name": "NRGkick Gen2 SIM",
        "device_ip": "192.168.1.100",
    }
