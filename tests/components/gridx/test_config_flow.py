"""Tests for the GridX config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from homeassistant.components.gridx.config_flow import _NoSystemsFoundError
from homeassistant.components.gridx.const import CONF_OEM, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import OEM, PASSWORD, USERNAME

from tests.common import MockConfigEntry


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    """Build an httpx.HTTPStatusError with the given status code."""
    response = MagicMock()
    response.status_code = status_code
    return httpx.HTTPStatusError(
        str(status_code), request=MagicMock(), response=response
    )


ERROR_CASES = [
    pytest.param(
        PermissionError("bad credentials"), "invalid_auth", id="permission-error"
    ),
    pytest.param(_http_status_error(401), "invalid_auth", id="http-401"),
    pytest.param(_http_status_error(500), "cannot_connect", id="http-500"),
    pytest.param(httpx.HTTPError("timeout"), "cannot_connect", id="httpx-error"),
    pytest.param(
        ConnectionError("network down"), "cannot_connect", id="connection-error"
    ),
    pytest.param(TimeoutError("timeout"), "cannot_connect", id="timeout"),
    pytest.param(_NoSystemsFoundError(), "no_systems", id="no-systems"),
    pytest.param(RuntimeError("unexpected"), "unknown", id="unexpected"),
]


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


@pytest.mark.parametrize(("side_effect", "expected_error"), ERROR_CASES)
async def test_user_step_errors(
    hass: HomeAssistant, side_effect: Exception, expected_error: str
) -> None:
    """Validation errors in the user step show the matching form error."""
    with patch(
        "homeassistant.components.gridx.config_flow._validate_credentials",
        new=AsyncMock(side_effect=side_effect),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


async def test_user_step_no_systems(hass: HomeAssistant) -> None:
    """Test that an account without systems shows the no_systems error."""
    connector = MagicMock()
    connector.retrieve_live_data = AsyncMock(return_value=[])
    connector.close = AsyncMock()
    with patch(
        "homeassistant.components.gridx.config_flow.async_create_connector",
        new=AsyncMock(return_value=connector),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_systems"}
    connector.close.assert_awaited_once()


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


async def test_reconfigure_updates_unique_id_on_username_change(
    hass: HomeAssistant,
) -> None:
    """Test that reconfigure updates unique_id and title when username changes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        unique_id=USERNAME.lower(),
        title=USERNAME,
    )
    entry.add_to_hass(hass)

    new_username = "changed@example.com"
    with patch(
        "homeassistant.components.gridx.config_flow._validate_credentials",
        new=AsyncMock(),
    ):
        result = await entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: new_username,
                CONF_PASSWORD: "new-password",
                CONF_OEM: OEM,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    updated_entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert updated_entry is not None
    assert updated_entry.unique_id == new_username.lower()
    assert updated_entry.title == new_username
    assert updated_entry.data[CONF_USERNAME] == new_username


@pytest.mark.parametrize(("side_effect", "expected_error"), ERROR_CASES)
async def test_reauth_errors(
    hass: HomeAssistant, side_effect: Exception, expected_error: str
) -> None:
    """Validation errors during reauth show the matching form error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        unique_id=USERNAME.lower(),
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.gridx.config_flow._validate_credentials",
        new=AsyncMock(side_effect=side_effect),
    ):
        result = await entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "new-password"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": expected_error}


@pytest.mark.parametrize(("side_effect", "expected_error"), ERROR_CASES)
async def test_reconfigure_errors(
    hass: HomeAssistant, side_effect: Exception, expected_error: str
) -> None:
    """Validation errors during reconfigure show the matching form error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        unique_id=USERNAME.lower(),
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.gridx.config_flow._validate_credentials",
        new=AsyncMock(side_effect=side_effect),
    ):
        result = await entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": expected_error}


async def test_validate_credentials_closes_client_on_connector_error(
    hass: HomeAssistant,
) -> None:
    """The httpx client is closed when connector creation fails."""
    httpx_client = MagicMock()
    httpx_client.aclose = AsyncMock()
    with (
        patch(
            "homeassistant.components.gridx.config_flow.create_async_httpx_client",
            return_value=httpx_client,
        ),
        patch(
            "homeassistant.components.gridx.config_flow.async_create_connector",
            new=AsyncMock(side_effect=PermissionError("bad credentials")),
        ),
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
    httpx_client.aclose.assert_awaited_once()
