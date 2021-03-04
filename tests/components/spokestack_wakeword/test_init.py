"""Tests for __init__ in the spokestack_wakeword component."""
from unittest import mock

import requests

from homeassistant.components import spokestack_wakeword
from homeassistant.components.spokestack_wakeword.const import DEFAULT_MODEL_URL, DOMAIN

from tests.common import MockConfigEntry


async def test_async_setup_entry(hass):
    """Test entry setup."""
    config = MockConfigEntry(
        domain=DOMAIN,
        data={"model_name": "test model", "model_url": DEFAULT_MODEL_URL},
    )
    with mock.patch(
        "homeassistant.components.spokestack_wakeword.build_pipeline",
        return_value=mock.MagicMock(),
    ):
        result = await spokestack_wakeword.async_setup_entry(hass, config)
        assert result


async def test_async_setup(hass):
    """Test integration setup."""
    with mock.patch(
        "homeassistant.components.spokestack_wakeword.build_pipeline",
        return_value=mock.MagicMock(),
    ):
        result = await spokestack_wakeword.async_setup(hass, {})
        assert result


async def test_service_start(hass):
    """Test the start service."""
    with mock.patch(
        "homeassistant.components.spokestack_wakeword.build_pipeline",
        return_value=mock.MagicMock(),
    ):
        await spokestack_wakeword.async_setup(hass, {})
        await hass.services.async_call(DOMAIN, "start", blocking=False)


async def test_service_run(hass):
    """Test the run service."""
    with mock.patch(
        "homeassistant.components.spokestack_wakeword.build_pipeline",
        return_value=mock.MagicMock(),
    ):
        await spokestack_wakeword.async_setup(hass, {})
        await hass.services.async_call(DOMAIN, "run", blocking=False)


async def test_service_stop(hass):
    """Test the stop service."""

    with mock.patch(
        "homeassistant.components.spokestack_wakeword.build_pipeline",
        return_value=mock.MagicMock(),
    ):
        await spokestack_wakeword.async_setup(hass, {})
        await hass.services.async_call(DOMAIN, "stop", blocking=False)


@mock.patch("homeassistant.components.spokestack_wakeword.build_pipeline")
async def test_async_setup_error(_mock, hass):
    """Test entry setup error."""
    config = MockConfigEntry(
        domain=DOMAIN,
        data={"model_name": "test model", "model_url": DEFAULT_MODEL_URL},
    )
    with mock.patch(
        "homeassistant.components.spokestack_wakeword._download_models",
        side_effect=requests.exceptions.RequestException(),
    ):
        result = await spokestack_wakeword.async_setup_entry(hass, config)
        assert not result
