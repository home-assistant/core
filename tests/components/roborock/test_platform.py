"""Test Roborock platform."""

import pytest

from homeassistant.components.roborock import VACUUM
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform
from .mock_data import HOME_DATA


@pytest.mark.asyncio
async def test_disable_include_shared(hass: HomeAssistant, bypass_api_fixture) -> None:
    """Tests devices are registered in the entity registry."""
    await setup_platform(hass, VACUUM, include_shared=False)
    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("vacuum.roborock_s7_maxv")
    assert entry.unique_id == HOME_DATA.devices[0].duid

    entry = entity_registry.async_get("vacuum.roborock_s7_maxv_shared")
    assert entry is None
