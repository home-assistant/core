"""Tests for the ALLNET config flow."""

from ipaddress import IPv4Address
from unittest.mock import AsyncMock, patch

from allnet.exceptions import (
    AllnetAuthenticationError,
    AllnetConnectionError,
    AllnetUnsupportedFirmwareError,
)
import pytest

from homeassistant.components.allnet.const import (
    CONF_DEVICE_PROFILE,
    CONF_USE_SSL,
    CONF_VERIFY_SSL,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
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


# ---------------------------------------------------------------------------
# user step
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_step_success(hass: HomeAssistant, mock_device_info) -> None:
    """Test the user step completes successfully."""
    with _patch_validate(mock_device_info):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: TEST_HOST,
                CONF_USE_SSL: False,
                CONF_VERIFY_SSL: True,
                CONF_DEVICE_PROFILE: "auto",
            },
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_HOST] == TEST_HOST
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


# ---------------------------------------------------------------------------
# zeroconf_confirm step
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zeroconf_confirm_success(hass: HomeAssistant, mock_device_info) -> None:
    """Test zeroconf confirm step creates a config entry."""
    with _patch_validate(mock_device_info):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "zeroconf"},
            data=_make_zeroconf_info(),
        )
        assert result["step_id"] == "zeroconf_confirm"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE_PROFILE: "auto"},
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_HOST] == TEST_HOST


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


# ---------------------------------------------------------------------------
# reauth step
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reauth_success(
    hass: HomeAssistant, setup_integration, mock_device_info
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
            return_value=mock_device_info,
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={CONF_USERNAME: "admin", CONF_PASSWORD: "newpass"},
            )

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
