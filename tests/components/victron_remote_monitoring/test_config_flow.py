"""Test the Victron VRM Solar Forecast config flow."""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch

from victron_vrm.exceptions import AuthenticationError, VictronVRMError

from homeassistant import config_entries
from homeassistant.components.victron_remote_monitoring.const import (
    CONF_API_KEY,
    CONF_SITE_ID,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


def _make_site(site_id: int, name: str = "ESS System") -> SimpleNamespace:
    """Create a minimal object with attributes used by the flow (id, name)."""
    return SimpleNamespace(id=site_id, name=name)


async def test_full_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the 2-step flow: token -> select site -> create entry."""
    site1 = _make_site(123456, "ESS")
    site2 = _make_site(987654, "Cabin")

    # Init user step
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    res = cast(dict[str, Any], result)
    assert res["type"] is FlowResultType.FORM
    assert res["step_id"] == "user"
    assert res["errors"] == {}

    # Submit API key, expect select_site form populated from list_sites
    with patch(
        "homeassistant.components.victron_remote_monitoring.config_flow.VRMClientHolder.list_sites",
        return_value=[site2, site1],  # will be sorted by name then id
    ):
        result = await hass.config_entries.flow.async_configure(
            res["flow_id"],
            {CONF_API_KEY: "test_token"},
        )
    res = cast(dict[str, Any], result)
    assert res["type"] is FlowResultType.FORM
    assert res["step_id"] == "select_site"

    # Select a site, expect create entry
    with patch(
        "homeassistant.components.victron_remote_monitoring.config_flow.VRMClientHolder.get_site",
        return_value=site1,
    ):
        result = await hass.config_entries.flow.async_configure(
            res["flow_id"],
            {CONF_SITE_ID: str(site1.id)},
        )
    res = cast(dict[str, Any], result)
    assert res["type"] is FlowResultType.CREATE_ENTRY
    assert res["title"] == f"VRM Forecast for {site1.name}"
    assert res["data"] == {CONF_API_KEY: "test_token", CONF_SITE_ID: site1.id}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_step_one_site_creates_entry_immediately(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """If only one site is available, the flow should create the entry right away."""
    site = _make_site(123456, "OnlySite")

    # Init user step
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    res = cast(dict[str, Any], result)
    assert res["type"] is FlowResultType.FORM
    assert res["step_id"] == "user"
    assert res["errors"] == {}

    # Submit API key; since there is only one site, we expect an entry to be created
    with patch(
        "homeassistant.components.victron_remote_monitoring.config_flow.VRMClientHolder.list_sites",
        return_value=[site],
    ):
        result = await hass.config_entries.flow.async_configure(
            res["flow_id"],
            {CONF_API_KEY: "test_token"},
        )
    res = cast(dict[str, Any], result)
    assert res["type"] is FlowResultType.CREATE_ENTRY
    assert res["title"] == f"VRM Forecast for {site.name}"
    assert res["data"] == {CONF_API_KEY: "test_token", CONF_SITE_ID: site.id}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_step_invalid_auth(hass: HomeAssistant) -> None:
    """Invalid token during user step shows invalid_auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.victron_remote_monitoring.config_flow.VRMClientHolder.list_sites",
        side_effect=AuthenticationError("bad token", status_code=401),
    ):
        result = await hass.config_entries.flow.async_configure(
            cast(dict[str, Any], result)["flow_id"],
            {CONF_API_KEY: "invalid"},
        )
    res = cast(dict[str, Any], result)
    assert res["type"] is FlowResultType.FORM
    assert res["step_id"] == "user"
    assert res["errors"] == {"base": "invalid_auth"}


async def test_user_step_cannot_connect(hass: HomeAssistant) -> None:
    """Server errors during user step show cannot_connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.victron_remote_monitoring.config_flow.VRMClientHolder.list_sites",
        side_effect=VictronVRMError("oops", status_code=500, response_data={}),
    ):
        result = await hass.config_entries.flow.async_configure(
            cast(dict[str, Any], result)["flow_id"],
            {CONF_API_KEY: "token"},
        )
    res = cast(dict[str, Any], result)
    assert res["type"] is FlowResultType.FORM
    assert res["step_id"] == "user"
    assert res["errors"] == {"base": "cannot_connect"}


async def test_user_step_no_sites(hass: HomeAssistant) -> None:
    """No sites available after token validation keeps user step with error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.victron_remote_monitoring.config_flow.VRMClientHolder.list_sites",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            cast(dict[str, Any], result)["flow_id"],
            {CONF_API_KEY: "token"},
        )
    res = cast(dict[str, Any], result)
    assert res["type"] is FlowResultType.FORM
    assert res["step_id"] == "user"
    assert res["errors"] == {"base": "no_sites"}


async def _start_flow_to_select_site(
    hass: HomeAssistant,
) -> tuple[str, list[SimpleNamespace]]:
    """Complete user step and return flow_id and sites."""
    sites = [_make_site(1, "A"), _make_site(2, "B")]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.victron_remote_monitoring.config_flow.VRMClientHolder.list_sites",
        return_value=sites,
    ):
        result = await hass.config_entries.flow.async_configure(
            cast(dict[str, Any], result)["flow_id"], {CONF_API_KEY: "token"}
        )
    res = cast(dict[str, Any], result)
    assert res["type"] is FlowResultType.FORM
    assert res["step_id"] == "select_site"
    return res["flow_id"], sites


async def test_select_site_invalid_auth(hass: HomeAssistant) -> None:
    """Invalid auth on site validation shows invalid_auth on select form."""
    flow_id, sites = await _start_flow_to_select_site(hass)
    with patch(
        "homeassistant.components.victron_remote_monitoring.config_flow.VRMClientHolder.get_site",
        side_effect=AuthenticationError("bad", status_code=403),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {CONF_SITE_ID: str(sites[0].id)}
        )
    res = cast(dict[str, Any], result)
    assert res["type"] is FlowResultType.FORM
    assert res["step_id"] == "select_site"
    assert res["errors"] == {"base": "invalid_auth"}


async def test_select_site_cannot_connect(hass: HomeAssistant) -> None:
    """Connection issues on site validation show cannot_connect."""
    flow_id, sites = await _start_flow_to_select_site(hass)
    with patch(
        "homeassistant.components.victron_remote_monitoring.config_flow.VRMClientHolder.get_site",
        side_effect=VictronVRMError("oops", status_code=500, response_data={}),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {CONF_SITE_ID: str(sites[0].id)}
        )
    res = cast(dict[str, Any], result)
    assert res["type"] is FlowResultType.FORM
    assert res["step_id"] == "select_site"
    assert res["errors"] == {"base": "cannot_connect"}


async def test_select_site_not_found(hass: HomeAssistant) -> None:
    """None returned from get_site shows site_not_found."""
    flow_id, sites = await _start_flow_to_select_site(hass)
    with patch(
        "homeassistant.components.victron_remote_monitoring.config_flow.VRMClientHolder.get_site",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {CONF_SITE_ID: str(sites[0].id)}
        )
    res = cast(dict[str, Any], result)
    assert res["type"] is FlowResultType.FORM
    assert res["step_id"] == "select_site"
    assert res["errors"] == {"base": "site_not_found"}


async def test_select_site_unknown_error(hass: HomeAssistant) -> None:
    """Unexpected error is surfaced as unknown on select_site form."""
    flow_id, sites = await _start_flow_to_select_site(hass)
    with patch(
        "homeassistant.components.victron_remote_monitoring.config_flow.VRMClientHolder.get_site",
        side_effect=ValueError("boom"),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {CONF_SITE_ID: str(sites[0].id)}
        )
    res = cast(dict[str, Any], result)
    assert res["type"] is FlowResultType.FORM
    assert res["step_id"] == "select_site"
    assert res["errors"] == {"base": "unknown"}


async def test_select_site_duplicate_aborts(hass: HomeAssistant) -> None:
    """Selecting an already configured site aborts during the select step (multi-site)."""
    site_id = 555
    # Existing entry with same site id

    existing = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "token", CONF_SITE_ID: site_id},
        unique_id=str(site_id),
        title="Existing",
    )
    existing.add_to_hass(hass)

    # Start flow and reach select_site
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.victron_remote_monitoring.config_flow.VRMClientHolder.list_sites",
        # Return multiple sites so the flow shows the selection step
        return_value=[_make_site(site_id, "Dup"), _make_site(777, "Other")],
    ):
        result = await hass.config_entries.flow.async_configure(
            cast(dict[str, Any], result)["flow_id"], {CONF_API_KEY: "token2"}
        )
    res = cast(dict[str, Any], result)
    assert res["type"] is FlowResultType.FORM
    assert res["step_id"] == "select_site"

    # Selecting the same site should abort before validation
    result = await hass.config_entries.flow.async_configure(
        res["flow_id"], {CONF_SITE_ID: str(site_id)}
    )
    res = cast(dict[str, Any], result)
    assert res["type"] is FlowResultType.ABORT
    assert res["reason"] == "already_configured"
