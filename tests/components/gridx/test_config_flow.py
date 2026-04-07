"""Tests for the GridX config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from homeassistant.components.gridx.const import CONF_OEM, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import OEM, PASSWORD, USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[MagicMock]:
    """Prevent actual setup during config flow tests."""
    with patch(
        "homeassistant.components.gridx.async_setup_entry",
        return_value=True,
    ) as m:
        yield m


async def test_user_step_success(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
) -> None:
    """Test a successful config flow with valid credentials."""
    with patch(
        "homeassistant.components.gridx.config_flow._validate_credentials",
        new=AsyncMock(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"] == {
        CONF_USERNAME: USERNAME,
        CONF_PASSWORD: PASSWORD,
        CONF_OEM: OEM,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_step_invalid_auth(hass: HomeAssistant) -> None:
    """Test that an auth failure shows the invalid_auth error."""
    with patch(
        "homeassistant.components.gridx.config_flow._validate_credentials",
        new=AsyncMock(side_effect=PermissionError("bad credentials")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: "wrong", CONF_OEM: OEM},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_step_cannot_connect(hass: HomeAssistant) -> None:
    """Test that a network error shows the cannot_connect error."""
    with patch(
        "homeassistant.components.gridx.config_flow._validate_credentials",
        new=AsyncMock(side_effect=ConnectionError("network down")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_step_duplicate(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
) -> None:
    """Test that configuring the same account twice is aborted."""
    with patch(
        "homeassistant.components.gridx.config_flow._validate_credentials",
        new=AsyncMock(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        )

        # Second attempt with the same username
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_reauth_success(hass: HomeAssistant) -> None:
    """Test successful re-authentication flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        unique_id=USERNAME.lower(),
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.gridx.config_flow._validate_credentials",
        new=AsyncMock(),
    ):
        result = await entry.start_reauth_flow(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "new-password"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated_entry is not None
    assert updated_entry.data[CONF_PASSWORD] == "new-password"


async def test_reauth_invalid_auth(hass: HomeAssistant) -> None:
    """Test re-authentication flow error handling for invalid auth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        unique_id=USERNAME.lower(),
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.gridx.config_flow._validate_credentials",
        new=AsyncMock(side_effect=PermissionError("bad credentials")),
    ):
        result = await entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "wrong"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reconfigure_success(hass: HomeAssistant) -> None:
    """Test successful reconfiguration flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        unique_id=USERNAME.lower(),
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.gridx.config_flow._validate_credentials",
        new=AsyncMock(),
    ):
        result = await entry.start_reconfigure_flow(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reconfigure"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: "new-password",
                CONF_OEM: OEM,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated_entry is not None
    assert updated_entry.data[CONF_PASSWORD] == "new-password"
    assert updated_entry.data[CONF_OEM] == OEM


async def test_reconfigure_cannot_connect(hass: HomeAssistant) -> None:
    """Test reconfiguration flow error handling for connectivity failures."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        unique_id=USERNAME.lower(),
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.gridx.config_flow._validate_credentials",
        new=AsyncMock(side_effect=ConnectionError("network down")),
    ):
        result = await entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_OEM: OEM,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_step_http_status_401(hass: HomeAssistant) -> None:
    """HTTPStatusError 401 from validate_credentials shows invalid_auth."""
    response = MagicMock()
    response.status_code = 401
    err = httpx.HTTPStatusError("401", request=MagicMock(), response=response)
    with patch(
        "homeassistant.components.gridx.config_flow._validate_credentials",
        new=AsyncMock(side_effect=err),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_step_http_status_500(hass: HomeAssistant) -> None:
    """HTTPStatusError 500 from validate_credentials shows cannot_connect."""
    response = MagicMock()
    response.status_code = 500
    err = httpx.HTTPStatusError("500", request=MagicMock(), response=response)
    with patch(
        "homeassistant.components.gridx.config_flow._validate_credentials",
        new=AsyncMock(side_effect=err),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_step_httpx_error(hass: HomeAssistant) -> None:
    """httpx.HTTPError from validate_credentials shows cannot_connect."""
    with patch(
        "homeassistant.components.gridx.config_flow._validate_credentials",
        new=AsyncMock(side_effect=httpx.HTTPError("timeout")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_step_unexpected_error(hass: HomeAssistant) -> None:
    """Unexpected error from validate_credentials shows unknown."""
    with patch(
        "homeassistant.components.gridx.config_flow._validate_credentials",
        new=AsyncMock(side_effect=RuntimeError("unexpected")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_reauth_http_error(hass: HomeAssistant) -> None:
    """httpx.HTTPError during reauth shows cannot_connect."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        unique_id=USERNAME.lower(),
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.gridx.config_flow._validate_credentials",
        new=AsyncMock(side_effect=httpx.HTTPError("timeout")),
    ):
        result = await entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "new-password"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "cannot_connect"}
