"""Fixtures for tests."""

import pytest

from homeassistant.core import HomeAssistant

from .common import ComponentFactory

from tests.async_mock import patch


@pytest.fixture()
def component_factory(hass: HomeAssistant):
    """Return a factory for initializing the gogogate2 api."""
    with patch(
        "homeassistant.components.gogogate2.common.GogoGate2Api"
    ) as gogogate2_api_mock:
        yield ComponentFactory(hass, gogogate2_api_mock)
