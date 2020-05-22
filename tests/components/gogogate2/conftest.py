"""Fixtures for tests."""

from mock import patch
import pytest

from homeassistant.core import HomeAssistant

from .common import ComponentFactory


@pytest.fixture()
def component_factory(hass: HomeAssistant):
    """Return a factory for initializing the gogogate2 api."""
    with patch(
        "homeassistant.components.gogogate2.common.GogoGate2Api"
    ) as gogogate2_api_mock:
        yield ComponentFactory(hass, gogogate2_api_mock)
