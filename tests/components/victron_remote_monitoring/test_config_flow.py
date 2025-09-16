"""Test the Victron VRM Solar Forecast config flow."""

from unittest.mock import AsyncMock, Mock

import pytest
from victron_vrm.exceptions import AuthenticationError, VictronVRMError

from homeassistant.components.victron_remote_monitoring.const import (
    CONF_API_TOKEN,
    CONF_SITE_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


def _make_site(site_id: int, name: str = "ESS System") -> Mock:
    """Return a mock site object exposing id and name attributes.

    Using a mock (instead of SimpleNamespace) helps ensure tests rely only on
    the attributes we explicitly define and will surface unexpected attribute
    access via mock assertions if the implementation changes.
    """
    site = Mock()
    site.id = site_id
    site.name = name
    return site


async def test_full_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_vrm_client: AsyncMock
) -> None:
    """Test the 2-step flow: token -> select site -> create entry."""
    site1 = _make_site(123456, "ESS")
    site2 = _make_site(987654, "Cabin")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    mock_vrm_client.users.list_sites = AsyncMock(return_value=[site2, site1])
    mock_vrm_client.users.get_site = AsyncMock(return_value=site1)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: "test_token"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_site"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SITE_ID: str(site1.id)}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"VRM for {site1.name}"
    assert result["data"] == {
        CONF_API_TOKEN: "test_token",
        CONF_SITE_ID: site1.id,
    }
    assert mock_setup_entry.call_count == 1


async def test_user_step_no_sites(
    hass: HomeAssistant, mock_vrm_client: AsyncMock
) -> None:
    """No sites available keeps user step with no_sites error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_vrm_client.users.list_sites = AsyncMock(return_value=[])
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: "token"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_sites"}

    # Provide a site afterwards and resubmit to complete the flow
    site = _make_site(999999, "Only Site")
    mock_vrm_client.users.list_sites = AsyncMock(return_value=[site])
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: "token"}
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {CONF_API_TOKEN: "token", CONF_SITE_ID: site.id}


@pytest.mark.parametrize(
    ("side_effect", "return_value", "expected_error"),
    [
        (AuthenticationError("ExpiredToken", status_code=403), None, "invalid_auth"),
        (
            VictronVRMError("Internal server error", status_code=500, response_data={}),
            None,
            "cannot_connect",
        ),
        (None, None, "site_not_found"),  # get_site returns None
        (ValueError("missing"), None, "unknown"),
    ],
)
async def test_select_site_errors(
    hass: HomeAssistant,
    mock_vrm_client: AsyncMock,
    side_effect: Exception | None,
    return_value: Mock | None,
    expected_error: str,
) -> None:
    """Parametrized select_site error scenarios."""
    sites = [_make_site(1, "A"), _make_site(2, "B")]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]
    mock_vrm_client.users.list_sites = AsyncMock(return_value=sites)
    if side_effect is not None:
        mock_vrm_client.users.get_site = AsyncMock(side_effect=side_effect)
    else:
        mock_vrm_client.users.get_site = AsyncMock(return_value=return_value)
    res_intermediate = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_API_TOKEN: "token"}
    )
    assert res_intermediate["step_id"] == "select_site"
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_SITE_ID: str(sites[0].id)}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_site"
    assert result["errors"] == {"base": expected_error}

    # Fix the error path by making get_site succeed and submit again
    good_site = _make_site(sites[0].id, sites[0].name)
    mock_vrm_client.users.get_site = AsyncMock(return_value=good_site)
    result_success = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_SITE_ID: str(sites[0].id)}
    )
    assert result_success["type"] is FlowResultType.CREATE_ENTRY
    assert result_success["data"] == {
        CONF_API_TOKEN: "token",
        CONF_SITE_ID: good_site.id,
    }


async def test_select_site_duplicate_aborts(
    hass: HomeAssistant, mock_vrm_client: AsyncMock
) -> None:
    """Selecting an already configured site aborts during the select step (multi-site)."""
    site_id = 555
    # Existing entry with same site id

    existing = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_TOKEN: "token", CONF_SITE_ID: site_id},
        unique_id=str(site_id),
        title="Existing",
    )
    existing.add_to_hass(hass)

    # Start flow and reach select_site
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_vrm_client.users.list_sites = AsyncMock(
        return_value=[_make_site(site_id, "Dup"), _make_site(777, "Other")]
    )
    mock_vrm_client.users.get_site = AsyncMock()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: "token2"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_site"

    # Selecting the same site should abort before validation (get_site not called)
    res_abort = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SITE_ID: str(site_id)}
    )
    assert res_abort["type"] is FlowResultType.ABORT
    assert res_abort["reason"] == "already_configured"
    assert mock_vrm_client.users.get_site.call_count == 0

    # Start a new flow selecting the other site to finish with a create entry
    result_new = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    other_site = _make_site(777, "Other")
    mock_vrm_client.users.list_sites = AsyncMock(return_value=[other_site])
    result_new2 = await hass.config_entries.flow.async_configure(
        result_new["flow_id"], {CONF_API_TOKEN: "token3"}
    )
    assert result_new2["type"] is FlowResultType.CREATE_ENTRY
    assert result_new2["data"] == {
        CONF_API_TOKEN: "token3",
        CONF_SITE_ID: other_site.id,
    }


async def test_reauth_flow_success(
    hass: HomeAssistant, mock_vrm_client: AsyncMock
) -> None:
    """Test successful reauthentication with new token."""
    # Existing configured entry
    site_id = 123456
    existing = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_TOKEN: "old_token", CONF_SITE_ID: site_id},
        unique_id=str(site_id),
        title="Existing",
    )
    existing.add_to_hass(hass)

    # Start reauth
    result = await existing.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # Provide new token; validate by returning the site
    site = _make_site(site_id, "ESS")
    mock_vrm_client.users.get_site = AsyncMock(return_value=site)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: "new_token"}
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    # Data updated
    assert existing.data[CONF_API_TOKEN] == "new_token"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (AuthenticationError("bad", status_code=401), "invalid_auth"),
        (VictronVRMError("down", status_code=500, response_data={}), "cannot_connect"),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_vrm_client: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Reauth shows errors when validation fails."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_TOKEN: "old", CONF_SITE_ID: 555},
        unique_id="555",
        title="Existing",
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    mock_vrm_client.users.get_site = AsyncMock(side_effect=side_effect)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: "bad"}
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": expected_error}

    # Provide a valid token afterwards to finish the reauth flow successfully
    good_site = _make_site(555, "Existing")
    mock_vrm_client.users.get_site = AsyncMock(return_value=good_site)
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_TOKEN: "new_valid"}
    )
    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"
