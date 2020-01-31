"""Initialization Test for the Carson Component."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import carson
from homeassistant.setup import async_setup_component

from .common import CONF_AND_FORM_CREDS

from tests.common import mock_coro

VALID_CONFIG = {"carson": CONF_AND_FORM_CREDS}


async def test_creating_entry_sets_up_devices(hass, success_requests_mock):
    """Test setting up carson loads device entities."""

    with patch(
        "homeassistant.components.carson.lock.async_setup_entry",
        return_value=mock_coro(True),
    ) as lock_mock_setup, patch(
        "homeassistant.components.carson.camera.async_setup_entry",
        return_value=mock_coro(True),
    ) as camera_mock_setup:
        result = await hass.config_entries.flow.async_init(
            carson.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        # Confirmation form
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONF_AND_FORM_CREDS
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        await hass.async_block_till_done()

    assert len(lock_mock_setup.mock_calls) == 1
    assert len(camera_mock_setup.mock_calls) == 1


async def test_configuring_carson_creates_entry(hass, success_requests_mock):
    """Test that specifying config will create an entry."""

    with patch(
        "homeassistant.components.carson.async_setup_entry",
        return_value=mock_coro(True),
    ) as mock_setup:
        await async_setup_component(hass, carson.DOMAIN, VALID_CONFIG)
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1


async def test_configuring_carson_wrong_creds_creates_no_entry(hass, requests_mock):
    """Test that a configuration with wrong credential will not create entry."""

    requests_mock.post(
        "https://api.carson.live/api/v1.4.1/auth/login/", status_code=401
    )

    with patch(
        "homeassistant.components.carson.async_setup_entry",
        return_value=mock_coro(True),
    ) as mock_setup:
        await async_setup_component(hass, carson.DOMAIN, VALID_CONFIG)
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 0
