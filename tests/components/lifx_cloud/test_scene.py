"""Test the LIFX Cloud scene."""

from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from homeassistant.components.lifx_cloud.scene import LifxCloudScene
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

SCENE_DATA = {"name": "Living room", "uuid": "abc-123"}


@pytest.fixture
def scene(hass: HomeAssistant) -> LifxCloudScene:
    """Return a LIFX Cloud scene entity."""
    return LifxCloudScene(hass, {"Authorization": "Bearer token"}, 10, SCENE_DATA)


async def test_activate(scene: LifxCloudScene) -> None:
    """The activate request goes out to the cloud."""
    with patch(
        "homeassistant.components.lifx_cloud.scene.async_get_clientsession"
    ) as session:
        session.return_value.put = AsyncMock()
        await scene.async_activate()

    assert session.return_value.put.call_count == 1


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(TimeoutError(), id="timeout"),
        pytest.param(aiohttp.ClientError("boom"), id="client_error"),
    ],
)
async def test_activate_failure_raises(scene: LifxCloudScene, error: Exception) -> None:
    """A failed activate raises HomeAssistantError."""
    with patch(
        "homeassistant.components.lifx_cloud.scene.async_get_clientsession"
    ) as session:
        session.return_value.put = AsyncMock(side_effect=error)
        with pytest.raises(HomeAssistantError):
            await scene.async_activate()
