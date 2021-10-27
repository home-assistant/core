"""Fixtures for tests."""

from unittest.mock import patch

import pytest

from homeassistant.core import HomeAssistant

from .common import ComponentFactory

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture()
def component_factory(
    hass: HomeAssistant, hass_client_no_auth, aioclient_mock: AiohttpClientMocker
):
    """Return a factory for initializing the withings component."""
    with patch(
        "homeassistant.components.withings.common.ConfigEntryWithingsApi"
    ) as api_class_mock:
        yield ComponentFactory(
            hass, api_class_mock, hass_client_no_auth, aioclient_mock
        )
