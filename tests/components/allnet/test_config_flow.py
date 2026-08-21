"""Tests for the ALLNET config flow."""

from dataclasses import replace
from ipaddress import IPv4Address
from unittest.mock import AsyncMock, MagicMock, patch

from allnet.exceptions import (
    AllnetAuthenticationError,
    AllnetConnectionError,
    AllnetInvalidResponseError,
    AllnetUnsupportedFirmwareError,
)
from allnet.models import DeviceInfo
import pytest

from homeassistant.components.allnet.config_flow import _validate_and_get_unique_id
from homeassistant.components.allnet.const import (
    CONF_DEVICE_PROFILE,
    CONF_USE_SSL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import TEST_HOST, TEST_UNIQUE_ID

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_zeroconf_info(
    host: str = TEST_HOST, name: str = "all3500"
) -> ZeroconfServiceInfo:
    """Return a ZeroconfServiceInfo for the given host/name."""
    ip = IPv4Address(host)
    return ZeroconfServiceInfo(
        ip_address=ip,
        ip_addresses=[ip],
        port=80,
        hostname=f"{name}.local.",
        type="_http._tcp.local.",
        name=f"{name}._http._tcp.local.",
        properties={},
    )


def _patch_validate(device_info):
    """Patch _validate_and_get_unique_id in the config_flow module."""
    return patch(
        "homeassistant.components.allnet.config_flow._validate_and_get_unique_id",
        new=AsyncMock(
            return_value=(
                device_info.unique_id,
                device_info.name or device_info.model or TEST_HOST,
            )
        ),
    )


def _patch_validate_error(exc):
    """Patch _validate_and_get_unique_id to raise exc."""
    return patch(
        "homeassistant.components.allnet.config_flow._validate_and_get_unique_id",
        new=AsyncMock(side_effect=exc),
    )


@pytest.mark.asyncio
async def test_validate_and_get_unique_id(
    hass: HomeAssistant,
    mock_allnet_client: MagicMock,
    mock_device_info: DeviceInfo,
) -> None:
    """Test validation creates a client and returns its device information."""
    mock_session = MagicMock()
    with (
        patch(
            "homeassistant.components.allnet.config_flow.AllnetClient",
            return_value=mock_allnet_client,
        ),
        patch(
            "homeassistant.components.allnet.config_flow.async_get_clientsession",
            return_value=mock_session,
        ) as mock_get_session,
    ):
        result = await _validate_and_get_unique_id(
            hass, TEST_HOST, "user", "password", True, False
        )

    assert result == (mock_device_info.unique_id, mock_device_info.name)
    mock_get_session.assert_called_once_with(hass, verify_ssl=False)


# ---------------------------------------------------------------------------
# user step
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_step_success(
    hass: HomeAssistant,
    mock_allnet_client: MagicMock,
    mock_device_info: DeviceInfo,
) -> None:
    """Test the user step completes successfully."""
    with (
        _patch_validate(mock_device_info),
        patch(
            "homeassistant.components.allnet.AllnetClient",
            return_value=mock_allnet_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: TEST_HOST,
                CONF_USERNAME: "user",
                CONF_PASSWORD: "password",
                CONF_USE_SSL: False,
                CONF_VERIFY_SSL: True,
                CONF_DEVICE_PROFILE: "auto",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_HOST] == TEST_HOST
    assert result2["data"][CONF_USERNAME] == "user"
    assert result2["data"][CONF_PASSWORD] == "password"
    assert result2["result"].unique_id == TEST_UNIQUE_ID


@pytest.mark.asyncio
async def test_user_step_cannot_connect(hass: HomeAssistant) -> None:
    """Test the user step shows cannot_connect error."""
    with _patch_validate_error(AllnetConnectionError("unreachable")):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: TEST_HOST,
                CONF_USE_SSL: False,
                CONF_VERIFY_SSL: True,
                CONF_DEVICE_PROFILE: "auto",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_user_step_invalid_auth(hass: HomeAssistant) -> None:
    """Test the user step shows invalid_auth error."""
    with _patch_validate_error(AllnetAuthenticationError("401")):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: TEST_HOST,
                CONF_USE_SSL: False,
                CONF_VERIFY_SSL: True,
                CONF_DEVICE_PROFILE: "auto",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "invalid_auth"


@pytest.mark.asyncio
async def test_user_step_unsupported_firmware(hass: HomeAssistant) -> None:
    """Test the user step shows unsupported_firmware error."""
    with _patch_validate_error(AllnetUnsupportedFirmwareError("old fw")):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: TEST_HOST,
                CONF_USE_SSL: False,
                CONF_VERIFY_SSL: True,
                CONF_DEVICE_PROFILE: "auto",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "unsupported_firmware"


@pytest.mark.asyncio
async def test_user_step_invalid_response(hass: HomeAssistant) -> None:
    """Test the user step shows an unknown error for an invalid response."""
    with _patch_validate_error(AllnetInvalidResponseError("invalid")):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: TEST_HOST,
                CONF_USE_SSL: False,
                CONF_VERIFY_SSL: True,
                CONF_DEVICE_PROFILE: "auto",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "unknown"


@pytest.mark.asyncio
async def test_user_step_already_configured(
    hass: HomeAssistant, mock_device_info, setup_integration
) -> None:
    """Test the user step aborts if the device is already configured."""
    with _patch_validate(mock_device_info):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: TEST_HOST,
                CONF_USE_SSL: False,
                CONF_VERIFY_SSL: True,
                CONF_DEVICE_PROFILE: "auto",
            },
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


# ---------------------------------------------------------------------------
# zeroconf step
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zeroconf_step_success(hass: HomeAssistant, mock_device_info) -> None:
    """Test zeroconf discovery shows the confirm form."""
    with _patch_validate(mock_device_info):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "zeroconf"},
            data=_make_zeroconf_info(),
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"


@pytest.mark.asyncio
async def test_zeroconf_step_non_allnet_name(hass: HomeAssistant) -> None:
    """Test zeroconf discovery aborts for non-allnet instance names."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data=_make_zeroconf_info(name="somedevice"),
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "not_allnet_device"


@pytest.mark.asyncio
async def test_zeroconf_step_already_configured(
    hass: HomeAssistant, mock_device_info, setup_integration
) -> None:
    """Test zeroconf aborts when device is already configured."""
    with _patch_validate(mock_device_info):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "zeroconf"},
            data=_make_zeroconf_info(),
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_zeroconf_step_authentication_required(hass: HomeAssistant) -> None:
    """Test zeroconf discovery continues when the device requires credentials."""
    with _patch_validate_error(AllnetAuthenticationError("401")):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "zeroconf"},
            data=_make_zeroconf_info(),
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exception"),
    [
        pytest.param(AllnetConnectionError("unreachable"), id="connection"),
        pytest.param(AllnetUnsupportedFirmwareError("old fw"), id="firmware"),
        pytest.param(AllnetInvalidResponseError("invalid"), id="invalid_response"),
    ],
)
async def test_zeroconf_step_cannot_connect(
    hass: HomeAssistant, exception: Exception
) -> None:
    """Test zeroconf discovery aborts when the JSON API is unavailable."""
    with _patch_validate_error(exception):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "zeroconf"},
            data=_make_zeroconf_info(),
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


# ---------------------------------------------------------------------------
# zeroconf_confirm step
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zeroconf_confirm_success(
    hass: HomeAssistant,
    mock_allnet_client: MagicMock,
    mock_device_info: DeviceInfo,
) -> None:
    """Test zeroconf confirm step creates a config entry."""
    with (
        _patch_validate(mock_device_info),
        patch(
            "homeassistant.components.allnet.AllnetClient",
            return_value=mock_allnet_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "zeroconf"},
            data=_make_zeroconf_info(),
        )
        assert result["step_id"] == "zeroconf_confirm"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "user",
                CONF_PASSWORD: "password",
                CONF_DEVICE_PROFILE: "auto",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_HOST] == TEST_HOST
    assert result2["data"][CONF_USERNAME] == "user"
    assert result2["data"][CONF_PASSWORD] == "password"


@pytest.mark.asyncio
async def test_zeroconf_confirm_invalid_auth(
    hass: HomeAssistant, mock_device_info
) -> None:
    """Test zeroconf confirm shows invalid_auth error when credentials wrong."""
    # First step succeeds (no auth)
    with _patch_validate(mock_device_info):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "zeroconf"},
            data=_make_zeroconf_info(),
        )
        assert result["step_id"] == "zeroconf_confirm"

    # Confirm step fails with auth error
    with _patch_validate_error(AllnetAuthenticationError("401")):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "user",
                CONF_PASSWORD: "wrong",
                CONF_DEVICE_PROFILE: "auto",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "invalid_auth"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        pytest.param(
            AllnetUnsupportedFirmwareError("old fw"),
            "unsupported_firmware",
            id="firmware",
        ),
        pytest.param(
            AllnetConnectionError("unreachable"), "cannot_connect", id="connection"
        ),
        pytest.param(
            AllnetInvalidResponseError("invalid"),
            "cannot_connect",
            id="invalid_response",
        ),
    ],
)
async def test_zeroconf_confirm_connection_errors(
    hass: HomeAssistant,
    mock_device_info: DeviceInfo,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test zeroconf confirmation displays validation errors."""
    with _patch_validate(mock_device_info):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "zeroconf"},
            data=_make_zeroconf_info(),
        )

    with _patch_validate_error(exception):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_DEVICE_PROFILE: "auto"}
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == expected_error


# ---------------------------------------------------------------------------
# reconfigure step
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reconfigure_success_removes_credentials(
    hass: HomeAssistant,
    mock_allnet_client: MagicMock,
    mock_device_info: DeviceInfo,
    setup_integration: ConfigEntry,
) -> None:
    """Test reconfiguration updates the entry and removes credentials."""
    entry = setup_integration
    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            CONF_PASSWORD: "old-password",
            CONF_USERNAME: "old-username",
        },
    )

    with (
        _patch_validate(mock_device_info),
        patch(
            "homeassistant.components.allnet.AllnetClient",
            return_value=mock_allnet_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": entry.entry_id},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.0.2.11",
                CONF_USE_SSL: True,
                CONF_VERIFY_SSL: False,
                CONF_DEVICE_PROFILE: "msr",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert entry.data == {
        CONF_HOST: "192.0.2.11",
        CONF_USE_SSL: True,
        CONF_VERIFY_SSL: False,
        CONF_DEVICE_PROFILE: "msr",
    }


@pytest.mark.asyncio
async def test_reconfigure_aborts_for_different_device(
    hass: HomeAssistant,
    mock_device_info: DeviceInfo,
    setup_integration: ConfigEntry,
) -> None:
    """Test reconfiguration aborts when the device ID does not match."""
    entry = setup_integration
    different_device_info = replace(mock_device_info, unique_id="001122334455")

    with _patch_validate(different_device_info):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": entry.entry_id},
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "192.0.2.11",
                CONF_USE_SSL: False,
                CONF_VERIFY_SSL: True,
                CONF_DEVICE_PROFILE: "auto",
            },
        )

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "unique_id_mismatch"


@pytest.mark.asyncio
async def test_reconfigure_success_updates_credentials(
    hass: HomeAssistant,
    mock_allnet_client: MagicMock,
    mock_device_info: DeviceInfo,
    setup_integration: ConfigEntry,
) -> None:
    """Test reconfiguration updates credentials when they are provided."""
    entry = setup_integration

    with (
        _patch_validate(mock_device_info),
        patch(
            "homeassistant.components.allnet.AllnetClient",
            return_value=mock_allnet_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": entry.entry_id},
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: TEST_HOST,
                CONF_USERNAME: "user",
                CONF_PASSWORD: "password",
                CONF_USE_SSL: False,
                CONF_VERIFY_SSL: True,
                CONF_DEVICE_PROFILE: "auto",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert entry.data[CONF_USERNAME] == "user"
    assert entry.data[CONF_PASSWORD] == "password"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        pytest.param(AllnetAuthenticationError("401"), "invalid_auth", id="auth"),
        pytest.param(
            AllnetUnsupportedFirmwareError("old fw"),
            "unsupported_firmware",
            id="firmware",
        ),
        pytest.param(
            AllnetConnectionError("unreachable"), "cannot_connect", id="connection"
        ),
        pytest.param(
            AllnetInvalidResponseError("invalid"), "unknown", id="invalid_response"
        ),
    ],
)
async def test_reconfigure_validation_errors(
    hass: HomeAssistant,
    setup_integration: ConfigEntry,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test reconfiguration displays validation errors."""
    with _patch_validate_error(exception):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reconfigure", "entry_id": setup_integration.entry_id},
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: TEST_HOST,
                CONF_USE_SSL: False,
                CONF_VERIFY_SSL: True,
                CONF_DEVICE_PROFILE: "auto",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == expected_error


# ---------------------------------------------------------------------------
# reauth step
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reauth_success(
    hass: HomeAssistant,
    mock_allnet_client: MagicMock,
    setup_integration: ConfigEntry,
    mock_device_info: DeviceInfo,
) -> None:
    """Test reauth flow updates credentials and reloads the entry."""
    entry = setup_integration

    with _patch_validate(mock_device_info):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "entry_id": entry.entry_id},
            data=entry.data,
        )
        assert result["step_id"] == "reauth_confirm"

        with patch(
            "homeassistant.components.allnet.AllnetClient",
            return_value=mock_allnet_client,
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={CONF_USERNAME: "admin", CONF_PASSWORD: "newpass"},
            )
            await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


@pytest.mark.asyncio
async def test_reauth_invalid_auth(hass: HomeAssistant, setup_integration) -> None:
    """Test reauth flow shows invalid_auth error on wrong credentials."""
    entry = setup_integration

    with _patch_validate_error(AllnetAuthenticationError("401")):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "entry_id": entry.entry_id},
            data=entry.data,
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: "admin", CONF_PASSWORD: "wrong"},
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "invalid_auth"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exception"),
    [
        pytest.param(AllnetConnectionError("unreachable"), id="connection"),
        pytest.param(AllnetInvalidResponseError("invalid"), id="invalid_response"),
    ],
)
async def test_reauth_connection_errors(
    hass: HomeAssistant, setup_integration: ConfigEntry, exception: Exception
) -> None:
    """Test reauthentication displays connection errors."""
    with _patch_validate_error(exception):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "entry_id": setup_integration.entry_id},
            data=setup_integration.data,
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: "admin", CONF_PASSWORD: "password"},
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_reauth_success_removes_empty_credentials(
    hass: HomeAssistant,
    mock_allnet_client: MagicMock,
    mock_device_info: DeviceInfo,
    setup_integration: ConfigEntry,
) -> None:
    """Test reauthentication removes credentials when submitted empty."""
    entry = setup_integration
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_USERNAME: "old", CONF_PASSWORD: "old"}
    )

    with _patch_validate(mock_device_info):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "entry_id": entry.entry_id},
            data=entry.data,
        )
        with patch(
            "homeassistant.components.allnet.AllnetClient",
            return_value=mock_allnet_client,
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={}
            )
            await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert CONF_USERNAME not in entry.data
    assert CONF_PASSWORD not in entry.data
