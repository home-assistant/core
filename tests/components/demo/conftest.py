"""demo conftest."""

from unittest.mock import patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture(autouse=True)
async def setup_homeassistant(hass: HomeAssistant):
    """Set up the homeassistant integration."""
    await async_setup_component(hass, "homeassistant", {})


@pytest.fixture
async def disable_platforms(hass: HomeAssistant) -> None:
    """Disable platforms to speed up tests."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [],
    ):
        yield
