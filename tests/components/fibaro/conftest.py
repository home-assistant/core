"""Test helpers."""
from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from pyfibaro.fibaro_scene import SceneModel
import pytest

from homeassistant.components.fibaro import DOMAIN, FIBARO_CONTROLLER, FIBARO_DEVICES
from homeassistant.config_entries import SOURCE_USER, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.fibaro.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="fibaro_scene")
def mock_scene() -> SceneModel:
    """Fixture for an individual scene."""
    scene = Mock(SceneModel)
    scene.fibaro_id = 1
    scene.name = "Test scene"
    scene.room_id = 1
    scene.visible = True
    return scene


async def setup_platform(
    hass: HomeAssistant,
    platform: Platform,
    room_name: str | None,
    scenes: list[SceneModel],
) -> ConfigEntry:
    """Set up the fibaro platform and prerequisites."""
    hass.config.components.add(DOMAIN)
    config_entry = ConfigEntry(
        1,
        DOMAIN,
        "Test",
        {},
        SOURCE_USER,
    )

    controller_mock = Mock()
    controller_mock.hub_serial = "HC2-111111"
    controller_mock.get_room_name.return_value = room_name

    for scene in scenes:
        scene.fibaro_controller = controller_mock

    hass.data[DOMAIN] = {
        config_entry.entry_id: {
            FIBARO_CONTROLLER: controller_mock,
            FIBARO_DEVICES: {Platform.SCENE: scenes},
        }
    }
    await hass.config_entries.async_forward_entry_setup(config_entry, platform)
    await hass.async_block_till_done()
    return config_entry
