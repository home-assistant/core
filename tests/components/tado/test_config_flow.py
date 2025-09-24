"""Test the Tado config flow."""

import asyncio
from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.tado.config_flow import TadoError
from homeassistant.components.tado.const import (
    CONF_FALLBACK,
    CONF_REFRESH_TOKEN,
    CONST_OVERLAY_TADO_DEFAULT,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_HOMEKIT, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import (
    ATTR_PROPERTIES_ID,
    ZeroconfServiceInfo,
)

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant,
    mock_tado_api: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full flow of the config flow."""

    event = asyncio.Event()

    async def mock_tado_api_device_activation() -> None:
        await asyncio.wait_for(event.wait(), timeout=5)

    mock_tado_api.device_activation = AsyncMock(
        side_effect=mock_tado_api_device_activation
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "user"

    # Indicate activation completed so the flow proceeds
    mock_tado_api.device_activation_status = "COMPLETED"
    event.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "home name"
    assert result["data"] == {CONF_REFRESH_TOKEN: "refresh"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_full_flow_reauth(
    hass: HomeAssistant,
    mock_tado_api: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full flow of the config when reauthticating."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ABC-123-DEF-456",
        data={CONF_REFRESH_TOKEN: "totally_refresh_for_reauth"},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    event = asyncio.Event()

    async def _activation():
        await asyncio.wait_for(event.wait(), timeout=5)

    mock_tado_api.device_activation = AsyncMock(side_effect=_activation)
    mock_tado_api.device_activation_status = "COMPLETED"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "user"

    event.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT  # expected for reauth

    updated = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated.data.get(CONF_REFRESH_TOKEN) == "refresh"


async def test_auth_timeout(
    hass: HomeAssistant,
    mock_tado_api: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the auth timeout and successful retry (fresh user flow)."""

    # First attempt: force a timeout by making activation fail immediately
    mock_tado_api.device_activation = AsyncMock(side_effect=Exception("timeout"))

    # Start the flow → it goes straight to SHOW_PROGRESS_DONE("timeout")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "timeout"

    # Prepare a successful path for the retry
    event = asyncio.Event()

    async def activation_ok():
        await asyncio.wait_for(event.wait(), timeout=5)

    mock_tado_api.device_activation = AsyncMock(side_effect=activation_ok)
    mock_tado_api.device_activation_status = "COMPLETED"
    mock_tado_api.device_verification_url = (
        "https://login.tado.com/oauth2/device?user_code=7BQ5ZQ"
    )

    # Show the timeout form
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "timeout"

    # Submit the timeout form → back to progress (new async behavior)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "user"

    # Unblock activation and finish
    event.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "home name"
    assert result["data"] == {CONF_REFRESH_TOKEN: "refresh"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_no_homes(hass: HomeAssistant, mock_tado_api: MagicMock) -> None:
    """Test the full flow of the config flow."""
    mock_tado_api.get_me.return_value.homes = []

    event = asyncio.Event()

    async def activation():
        await asyncio.wait_for(event.wait(), timeout=5)

    mock_tado_api.device_activation = AsyncMock(side_effect=activation)
    mock_tado_api.device_activation_status = "COMPLETED"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "user"

    event.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_homes"


async def test_tado_creation(hass: HomeAssistant) -> None:
    """Test we handle Form Exceptions."""

    with patch(
        "homeassistant.components.tado.config_flow.Tado",
        side_effect=TadoError("Test exception"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (Exception, "timeout"),
        (TadoError, "timeout"),
    ],
)
async def test_wait_for_login_exception(
    hass: HomeAssistant,
    mock_tado_api: MagicMock,
    exception: Exception,
    error: str,
) -> None:
    """Test that an exception in wait for login is handled properly."""
    mock_tado_api.device_activation.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == error


async def test_options_flow(
    hass: HomeAssistant,
    mock_tado_api: MagicMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config flow options."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_FALLBACK: CONST_OVERLAY_TADO_DEFAULT},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_FALLBACK: CONST_OVERLAY_TADO_DEFAULT}


async def test_homekit(hass: HomeAssistant, mock_tado_api: MagicMock) -> None:
    """Test that we abort from homekit if tado is already setup."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_HOMEKIT},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={ATTR_PROPERTIES_ID: "AA:BB:CC:DD:EE:FF"},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "homekit_confirm"

    event = asyncio.Event()

    async def activation():
        await asyncio.wait_for(event.wait(), timeout=5)

    mock_tado_api.device_activation = AsyncMock(side_effect=activation)
    mock_tado_api.device_activation_status = "COMPLETED"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "user"

    event.set()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "1"


async def test_homekit_already_setup(
    hass: HomeAssistant, mock_tado_api: MagicMock
) -> None:
    """Test that we abort from homekit if tado is already setup."""

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_USERNAME: "mock", CONF_PASSWORD: "mock"}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_HOMEKIT},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="mock_hostname",
            name="mock_name",
            port=None,
            properties={ATTR_PROPERTIES_ID: "AA:BB:CC:DD:EE:FF"},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
