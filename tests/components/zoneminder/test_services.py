"""Tests for ZoneMinder service calls."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import voluptuous as vol

from homeassistant.components.zoneminder.const import DOMAIN
from homeassistant.const import ATTR_ID, ATTR_NAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import MOCK_HOST, MOCK_HOST_2, create_mock_zm_client


async def test_set_run_state_service_registered(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
) -> None:
    """Test set_run_state service is registered after setup."""
    assert await async_setup_component(hass, DOMAIN, single_server_config)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, "set_run_state")


async def test_set_run_state_valid_call(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
) -> None:
    """Test valid set_run_state call sets state on correct ZM client."""
    assert await async_setup_component(hass, DOMAIN, single_server_config)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        "set_run_state",
        {ATTR_ID: MOCK_HOST, ATTR_NAME: "Away"},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_zoneminder_client.set_active_state.assert_called_once_with("Away")


async def test_set_run_state_multi_server_targets_correct_server(
    hass: HomeAssistant, multi_server_config: dict
) -> None:
    """Test set_run_state targets specific server by id."""
    clients: dict[str, MagicMock] = {}

    def make_client(*args, **kwargs):
        client = create_mock_zm_client()
        # Extract hostname from the server_origin (first positional arg)
        origin = args[0]
        hostname = origin.split("://")[1]
        clients[hostname] = client
        return client

    with patch(
        "homeassistant.components.zoneminder.ZoneMinder",
        side_effect=make_client,
    ):
        assert await async_setup_component(hass, DOMAIN, multi_server_config)
        await hass.async_block_till_done()

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
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
) -> None:
    """Test service call with missing required fields is rejected."""
    assert await async_setup_component(hass, DOMAIN, single_server_config)
    await hass.async_block_till_done()

    with pytest.raises(vol.MultipleInvalid):
        await hass.services.async_call(
            DOMAIN,
            "set_run_state",
            {ATTR_ID: MOCK_HOST},  # Missing ATTR_NAME
            blocking=True,
        )


async def test_set_run_state_invalid_host(
    hass: HomeAssistant,
    mock_zoneminder_client: MagicMock,
    single_server_config: dict,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test service call with invalid host logs error.

    Regression: services.py logs error but doesn't return early,
    so it also raises KeyError when trying to access the invalid host.
    """
    assert await async_setup_component(hass, DOMAIN, single_server_config)
    await hass.async_block_till_done()

    with pytest.raises(KeyError):
        await hass.services.async_call(
            DOMAIN,
            "set_run_state",
            {ATTR_ID: "invalid.host", ATTR_NAME: "Away"},
            blocking=True,
        )

    assert "Invalid ZoneMinder host provided" in caplog.text
