"""Tests for the NRGkick config flow."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.nrgkick.api import (
    NRGkickApiClientAuthenticationError,
    NRGkickApiClientCommunicationError,
    NRGkickApiClientError,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import create_mock_config_entry


async def test_form(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test we can setup when authentication is required."""
    result = await hass.config_entries.flow.async_init(
        "nrgkick", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.100"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "user_auth"

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
            {
                CONF_USERNAME: "test_user",
                CONF_PASSWORD: "test_pass",
            },
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
            {CONF_HOST: "192.168.1.100"},
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "user_auth"

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result3["type"] == data_entry_flow.FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_auth"}


async def test_user_auth_step_cannot_connect(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test user auth step reports cannot_connect."""
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
            {CONF_HOST: "192.168.1.100"},
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "user_auth"

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


async def test_user_auth_step_unknown_error(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test user auth step reports unknown on unexpected error."""
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
            {CONF_HOST: "192.168.1.100"},
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "user_auth"

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    assert result3["type"] == data_entry_flow.FlowResultType.FORM
    assert result3["errors"] == {"base": "unknown"}


async def test_user_auth_step_no_serial_number(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test user auth step reports no_serial_number when missing."""
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
            {CONF_HOST: "192.168.1.100"},
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "user_auth"

    mock_nrgkick_api.test_connection.side_effect = None
    mock_nrgkick_api.get_info.return_value = {
        "general": {"device_name": "NRGkick Test"}
    }

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    assert result3["type"] == data_entry_flow.FlowResultType.FORM
    assert result3["errors"] == {"base": "no_serial_number"}


async def test_form_no_serial_number(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test we handle missing serial number."""
    result = await hass.config_entries.flow.async_init(
        "nrgkick", context={"source": config_entries.SOURCE_USER}
    )

    mock_nrgkick_api.get_info.return_value = {
        "general": {
            "device_name": "NRGkick Test",
            # serial_number missing
            "rated_current": 32.0,
        }
    }

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.100"},
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "no_serial_number"}


async def test_form_unknown_exception(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test we handle unknown exception."""
    result = await hass.config_entries.flow.async_init(
        "nrgkick", context={"source": config_entries.SOURCE_USER}
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientError

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


async def test_reauth_flow_invalid_auth(hass: HomeAssistant, mock_nrgkick_api) -> None:
    """Test reauth flow with invalid authentication."""
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
        },
        data=entry.data,
    )

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientAuthenticationError

    with patch(
        "homeassistant.components.nrgkick.config_flow.NRGkickAPI",
        return_value=mock_nrgkick_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "wrong_user",
                CONF_PASSWORD: "wrong_pass",
            },
        )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reauth_flow_unknown_exception(
    hass: HomeAssistant, mock_nrgkick_api
) -> None:
    """Test reauth flow with unexpected exception."""
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

    mock_nrgkick_api.test_connection.side_effect = NRGkickApiClientError

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
    assert result2["errors"] == {"base": "unknown"}


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
