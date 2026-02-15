"""Tests for ZoneMinder service calls."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import voluptuous as vol

from homeassistant.components.zoneminder.const import DOMAIN
from homeassistant.components.zoneminder.services import _set_active_state
from homeassistant.const import ATTR_ID, ATTR_NAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from .conftest import MOCK_HOST, MOCK_HOST_2, create_mock_zm_client


async def _setup_zm(hass: HomeAssistant, config: dict) -> dict:
    """Set up ZM component and return mapping of host -> client."""
    clients = {}

    def make_client(*args, **kwargs):
        client = create_mock_zm_client()
        # Extract hostname from the server_origin (first positional arg)
        origin = args[0]
        # origin is like "http://zm.example.com"
        hostname = origin.split("://")[1]
        clients[hostname] = client
        return client

    with patch(
        "homeassistant.components.zoneminder.ZoneMinder",
        side_effect=make_client,
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    return clients


async def test_set_run_state_service_registered(
    hass: HomeAssistant, single_server_config
) -> None:
    """Test set_run_state service is registered after setup."""
    await _setup_zm(hass, single_server_config)

    assert hass.services.has_service(DOMAIN, "set_run_state")


async def test_set_run_state_valid_call(
    hass: HomeAssistant, single_server_config
) -> None:
    """Test valid set_run_state call sets state on correct ZM client."""
    clients = await _setup_zm(hass, single_server_config)

    await hass.services.async_call(
        DOMAIN,
        "set_run_state",
        {ATTR_ID: MOCK_HOST, ATTR_NAME: "Away"},
        blocking=True,
    )
    await hass.async_block_till_done()

    clients[MOCK_HOST].set_active_state.assert_called_once_with("Away")


async def test_set_run_state_multi_server_targets_correct_server(
    hass: HomeAssistant, multi_server_config
) -> None:
    """Test set_run_state targets specific server by id."""
    clients = await _setup_zm(hass, multi_server_config)

    await hass.services.async_call(
        DOMAIN,
        "set_run_state",
        {ATTR_ID: MOCK_HOST_2, ATTR_NAME: "Home"},
        blocking=True,
    )
    await hass.async_block_till_done()

    # Only the second server should have been called
    clients[MOCK_HOST_2].set_active_state.assert_called_once_with("Home")
    clients[MOCK_HOST].set_active_state.assert_not_called()


async def test_set_run_state_missing_fields_rejected(
    hass: HomeAssistant, single_server_config
) -> None:
    """Test service call with missing required fields is rejected."""
    await _setup_zm(hass, single_server_config)

    with pytest.raises(vol.MultipleInvalid):
        await hass.services.async_call(
            DOMAIN,
            "set_run_state",
            {ATTR_ID: MOCK_HOST},  # Missing ATTR_NAME
            blocking=True,
        )


async def test_set_run_state_invalid_host(
    hass: HomeAssistant, single_server_config, caplog: pytest.LogCaptureFixture
) -> None:
    """Test service call with invalid host logs error.

    Regression: services.py logs error but doesn't return early,
    so it also raises KeyError when trying to access the invalid host.
    """
    await _setup_zm(hass, single_server_config)

    with pytest.raises(KeyError):
        await hass.services.async_call(
            DOMAIN,
            "set_run_state",
            {ATTR_ID: "invalid.host", ATTR_NAME: "Away"},
            blocking=True,
        )

    assert "Invalid ZoneMinder host provided" in caplog.text


def test_set_active_state_failure_logs_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test set_active_state failure logs error."""
    client = create_mock_zm_client()
    client.set_active_state.return_value = False
    hass.data[DOMAIN] = {MOCK_HOST: client}

    mock_call = MagicMock(spec=ServiceCall)
    mock_call.data = {ATTR_ID: MOCK_HOST, ATTR_NAME: "Away"}
    mock_call.hass = hass

    _set_active_state(mock_call)

    assert "Unable to change ZoneMinder state" in caplog.text


@pytest.mark.xfail(
    reason="BUG-01: _set_active_state missing return after invalid host check"
)
async def test_set_run_state_invalid_host_graceful(
    hass: HomeAssistant, single_server_config, caplog: pytest.LogCaptureFixture
) -> None:
    """Invalid host should log error and return without exception.

    The service handler logs an error for an invalid host but does not return
    early. Execution falls through and raises KeyError.
    """
    await _setup_zm(hass, single_server_config)

    # Desired behavior: no exception raised, just a log message
    await hass.services.async_call(
        DOMAIN,
        "set_run_state",
        {ATTR_ID: "invalid.host", ATTR_NAME: "Away"},
        blocking=True,
    )

    assert "Invalid ZoneMinder host provided" in caplog.text
