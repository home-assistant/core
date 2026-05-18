"""Tests for FritzBox VPN config flow (user, reauth, validation)."""

from unittest.mock import AsyncMock, patch

import pytest
import voluptuous as vol
from custom_components.fritzbox_vpn.const import DOMAIN
from custom_components.fritzbox_vpn.flow_forms import (
    CannotConnect,
    InvalidAuth,
    validate_host,
    validate_input,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from tests.fixtures import MOCK_HOST, MOCK_PASSWORD, MOCK_USERNAME


def test_validate_host_accepts_ip_and_hostname() -> None:
    """Host validation accepts IPv4 and simple hostnames."""
    assert validate_host("192.168.178.1") == "192.168.178.1"
    assert validate_host("fritz.box") == "fritz.box"


def test_validate_host_rejects_invalid() -> None:
    """Host validation rejects empty and malformed values."""
    with pytest.raises(vol.Invalid):
        validate_host("")
    with pytest.raises(vol.Invalid):
        validate_host(".invalid")


@pytest.mark.asyncio
async def test_user_flow_create_entry(hass: HomeAssistant) -> None:
    """User flow creates config entry after successful validation."""
    with patch(
        "custom_components.fritzbox_vpn.config_flow.get_existing_fritz_config",
        new=AsyncMock(return_value=None),
    ), patch(
        "custom_components.fritzbox_vpn.config_flow.validate_input",
        new=AsyncMock(return_value={"title": f"Fritz!Box VPN ({MOCK_HOST})"}),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: MOCK_USERNAME,
                CONF_PASSWORD: MOCK_PASSWORD,
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == MOCK_HOST


@pytest.mark.asyncio
async def test_user_flow_invalid_auth(hass: HomeAssistant) -> None:
    """User flow shows invalid_auth when validation fails."""
    with patch(
        "custom_components.fritzbox_vpn.config_flow.get_existing_fritz_config",
        new=AsyncMock(return_value=None),
    ), patch(
        "custom_components.fritzbox_vpn.config_flow.validate_input",
        new=AsyncMock(side_effect=InvalidAuth),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: MOCK_USERNAME,
                CONF_PASSWORD: "wrong",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


@pytest.mark.asyncio
async def test_user_flow_invalid_host(hass: HomeAssistant) -> None:
    """User flow shows invalid_host for malformed host."""
    with patch(
        "custom_components.fritzbox_vpn.config_flow.get_existing_fritz_config",
        new=AsyncMock(return_value=None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: ".bad-host",
                CONF_USERNAME: MOCK_USERNAME,
                CONF_PASSWORD: MOCK_PASSWORD,
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"][CONF_HOST] == "invalid_host"


@pytest.mark.asyncio
async def test_reauth_updates_credentials(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Reauth flow updates entry data after successful validation."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.fritzbox_vpn.config_flow.validate_input",
        new=AsyncMock(return_value={"title": mock_config_entry.title}),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": SOURCE_REAUTH,
                "entry_id": mock_config_entry.entry_id,
                "unique_id": mock_config_entry.unique_id,
            },
            data=mock_config_entry.data,
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "new-user", CONF_PASSWORD: "new-pass"},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert hass.config_entries.async_get_entry(mock_config_entry.entry_id).data[
        CONF_USERNAME
    ] == "new-user"


@pytest.mark.asyncio
async def test_validate_input_maps_auth_error(hass: HomeAssistant) -> None:
    """validate_input raises InvalidAuth on login failure."""
    session_mock = AsyncMock()
    session_mock.async_get_session = AsyncMock(
        side_effect=ValueError("Login failed: Invalid SID")
    )
    session_mock.async_close = AsyncMock()

    with patch(
        "custom_components.fritzbox_vpn.flow_forms.FritzBoxVPNSession",
        return_value=session_mock,
    ):
        with pytest.raises(InvalidAuth):
            await validate_input(
                hass,
                {
                    CONF_HOST: MOCK_HOST,
                    CONF_USERNAME: MOCK_USERNAME,
                    CONF_PASSWORD: MOCK_PASSWORD,
                },
            )


@pytest.mark.asyncio
async def test_user_autoconfig_invalid_auth(hass: HomeAssistant) -> None:
    """User flow shows form with invalid_auth when Fritz autoconfig fails."""
    with patch(
        "custom_components.fritzbox_vpn.config_flow.get_existing_fritz_config",
        new=AsyncMock(
            return_value={
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: MOCK_USERNAME,
                CONF_PASSWORD: MOCK_PASSWORD,
            }
        ),
    ), patch(
        "custom_components.fritzbox_vpn.config_flow.validate_input",
        new=AsyncMock(side_effect=InvalidAuth),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


@pytest.mark.asyncio
async def test_user_autoconfig_cannot_connect(hass: HomeAssistant) -> None:
    """User flow shows form with cannot_connect when Fritz autoconfig fails."""
    with patch(
        "custom_components.fritzbox_vpn.config_flow.get_existing_fritz_config",
        new=AsyncMock(
            return_value={
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: MOCK_USERNAME,
                CONF_PASSWORD: MOCK_PASSWORD,
            }
        ),
    ), patch(
        "custom_components.fritzbox_vpn.config_flow.validate_input",
        new=AsyncMock(side_effect=CannotConnect),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_user_autoconfig_unknown_error(hass: HomeAssistant) -> None:
    """User flow shows unknown error when autoconfig raises unexpectedly."""
    with patch(
        "custom_components.fritzbox_vpn.config_flow.get_existing_fritz_config",
        new=AsyncMock(
            return_value={
                CONF_HOST: MOCK_HOST,
                CONF_USERNAME: MOCK_USERNAME,
                CONF_PASSWORD: MOCK_PASSWORD,
            }
        ),
    ), patch(
        "custom_components.fritzbox_vpn.config_flow.validate_input",
        new=AsyncMock(side_effect=RuntimeError("unexpected")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"


@pytest.mark.asyncio
async def test_reauth_shows_error_on_validation_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Reauth confirm shows form again when validation fails."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.fritzbox_vpn.config_flow.validate_input",
        new=AsyncMock(side_effect=CannotConnect),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": SOURCE_REAUTH,
                "entry_id": mock_config_entry.entry_id,
                "unique_id": mock_config_entry.unique_id,
            },
            data=mock_config_entry.data,
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: "wrong"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_validate_input_maps_connect_error(hass: HomeAssistant) -> None:
    """validate_input raises CannotConnect on connection errors."""
    session_mock = AsyncMock()
    session_mock.async_get_session = AsyncMock(
        side_effect=ConnectionError("Failed to get login page")
    )
    session_mock.async_close = AsyncMock()

    with patch(
        "custom_components.fritzbox_vpn.flow_forms.FritzBoxVPNSession",
        return_value=session_mock,
    ):
        with pytest.raises(CannotConnect):
            await validate_input(
                hass,
                {
                    CONF_HOST: MOCK_HOST,
                    CONF_USERNAME: MOCK_USERNAME,
                    CONF_PASSWORD: MOCK_PASSWORD,
                },
            )
