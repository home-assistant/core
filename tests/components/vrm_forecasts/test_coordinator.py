"""Tests for the VRM Forecasts coordinator."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from victron_vrm.exceptions import AuthenticationError, VictronVRMError

from homeassistant.components.vrm_forecasts.coordinator import (
    VRMForecastsDataUpdateCoordinator,
    VRMForecastStore,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import CONST_FORECAST_RECORDS

from tests.common import MockConfigEntry


async def test_coordinator_update_success(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Coordinator returns forecast store on successful update."""
    coordinator = VRMForecastsDataUpdateCoordinator(hass, mock_config_entry)

    # Use the default autouse get_forecast patch from conftest
    data = await coordinator._async_update_data()

    assert isinstance(data, VRMForecastStore)
    # Sanity checks derived from the fixture
    assert data.site_id == mock_config_entry.data["site_id"]
    # Yesterday total is sum of the first two records in the fixture
    yesterday_total = CONST_FORECAST_RECORDS[0][1] + CONST_FORECAST_RECORDS[1][1]
    assert data.solar.yesterday_total == pytest.approx(yesterday_total)
    assert data.consumption.yesterday_total == pytest.approx(yesterday_total)


async def test_coordinator_maps_auth_error(
    hass: HomeAssistant, mock_config_entry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AuthenticationError is mapped to ConfigEntryAuthFailed."""

    async def raise_auth(_client, _site_id):
        raise AuthenticationError("bad token")

    monkeypatch.setattr(
        "homeassistant.components.vrm_forecasts.coordinator.get_forecast",
        raise_auth,
    )

    coordinator = VRMForecastsDataUpdateCoordinator(hass, mock_config_entry)

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_coordinator_maps_connection_error(
    hass: HomeAssistant, mock_config_entry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """VictronVRMError is mapped to UpdateFailed."""

    async def raise_conn(_client, _site_id):
        raise VictronVRMError("boom")

    monkeypatch.setattr(
        "homeassistant.components.vrm_forecasts.coordinator.get_forecast",
        raise_conn,
    )

    coordinator = VRMForecastsDataUpdateCoordinator(hass, mock_config_entry)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_token_type_based_on_key_format(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Ensure token_type passed to client matches token format (JWT or Token)."""
    # First, with a JWT-like token (two dots) -> Bearer
    jwt_entry = MockConfigEntry(
        domain="vrm_forecasts",
        data={"api_key": "not.a.jwt", "site_id": 123456},
    )

    with patch(
        "homeassistant.components.vrm_forecasts.coordinator.VictronVRMClient"
    ) as m:
        VRMForecastsDataUpdateCoordinator(hass, jwt_entry)
        assert m.call_args is not None
        kwargs = m.call_args.kwargs
        assert kwargs.get("token_type") == "Bearer"  # looks like a JWT (two dots)

    # With a simple token -> Token
    token_entry = MockConfigEntry(
        domain="vrm_forecasts",
        data={"api_key": "abc123", "site_id": 123456},
    )

    with patch(
        "homeassistant.components.vrm_forecasts.coordinator.VictronVRMClient"
    ) as m:
        VRMForecastsDataUpdateCoordinator(hass, token_entry)
        assert m.call_args is not None
        kwargs = m.call_args.kwargs
        assert kwargs.get("token_type") == "Token"
