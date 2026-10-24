"""Synthetic direct-credential onboarding regressions."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.application_credentials import DATA_COMPONENT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.mark.usefixtures("recorder_mock", "mock_setup_entry")
@pytest.mark.parametrize("source", ["user", "reconfigure"])
async def test_direct_credentials(hass: HomeAssistant, source: str) -> None:
    """Partial pairs stay in the same flow; complete pairs use native registry."""
    assert await async_setup_component(hass, "application_credentials", {})
    hass.config.external_url = "https://ha.example.com"
    old = MockConfigEntry(
        domain="solaredge",
        title="Preserved",
        unique_id="preserved",
        data={"site_id": "123", "api_key": "synthetic-v1"},
    )
    context = {"source": source}
    if source == "reconfigure":
        old.add_to_hass(hass)
        context["entry_id"] = old.entry_id
    result = await hass.config_entries.flow.async_init("solaredge", context=context)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"use_oauth": True, **({"site_id": "123"} if source == "user" else {})},
    )
    assert result["step_id"] == "oauth_application"
    flow_id = result["flow_id"]
    with patch(
        "homeassistant.components.solaredge.config_flow.SolarEdgeConfigFlow._async_check_site",
        new_callable=AsyncMock,
    ) as legacy:
        for data in (
            {},
            {"client_id": "synthetic-client"},
            {"client_secret": "synthetic-secret"},
            {"client_id": " ", "client_secret": " "},
        ):
            result = await hass.config_entries.flow.async_configure(flow_id, data)
            assert result["step_id"] == "oauth_application"
            assert result["errors"] == {"base": "oauth_credentials_required"}
            assert result["flow_id"] == flow_id
        legacy.assert_not_awaited()
    assert not hass.data[DATA_COMPONENT].async_items()
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"client_id": "synthetic-client", "client_secret": "synthetic-secret"}
    )
    assert result["type"] == "external"
    assert (
        "https://ha.example.com/auth/external/callback" in result["url"]
        or "https%3A%2F%2Fha.example.com%2Fauth%2Fexternal%2Fcallback" in result["url"]
    )
    items = hass.data[DATA_COMPONENT].async_items()
    assert len(items) == 1
    assert items[0]["client_secret"] == "synthetic-secret"
    assert old.data == {"site_id": "123", "api_key": "synthetic-v1"}
    assert old.title == "Preserved"
