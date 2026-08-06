"""Tests for the Tewke integration utilities."""

from unittest.mock import AsyncMock, MagicMock, patch

from pytewke import ConfigData, EnergyData, RadarData, Scene, SensorData, Target
from pytewke.error import PyTewkeObserveError

from homeassistant.components.tewke.const import DOMAIN
from homeassistant.components.tewke.coordinator import TewkeCoordinatorData
from homeassistant.components.tewke.data import TewkeData
from homeassistant.components.tewke.util import (
    _ha_to_tewke_brightness,
    _tewke_to_ha_brightness,
    _TewkeObserver,
    async_setup_observe,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


def test_tewke_to_ha_brightness() -> None:
    """Test converting Tewke brightness to HA brightness."""
    assert _tewke_to_ha_brightness(0) == 0
    assert _tewke_to_ha_brightness(50) == 128
    assert _tewke_to_ha_brightness(100) == 255
    # Out of bounds
    assert _tewke_to_ha_brightness(-10) == 0
    assert _tewke_to_ha_brightness(110) == 255


def test_ha_to_tewke_brightness() -> None:
    """Test converting HA brightness to Tewke brightness."""
    assert _ha_to_tewke_brightness(0) == 0
    assert _ha_to_tewke_brightness(128) == 50
    assert _ha_to_tewke_brightness(255) == 100
    # Out of bounds
    assert _ha_to_tewke_brightness(-10) == 0
    assert _ha_to_tewke_brightness(300) == 100


async def test_async_setup_observe_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tap: AsyncMock,
) -> None:
    """Test setting up CoAP observations successfully."""
    mock_config_entry.runtime_data = TewkeData(
        host="test_host",
        coordinator=AsyncMock(),
        tap=mock_tap,
        scenes={
            "scene1": Scene(id="scene1", name="Scene 1", isActive=False, brightness=0),
        },
        pending_scenes={},
    )

    coordinator = AsyncMock()
    coordinator.data = {"scenes_all": {"scene1": Scene.model_construct(id="scene1")}}

    mock_tap._observation_manager = AsyncMock()

    with patch("homeassistant.components.tewke.util._TewkeObserver") as mock_observer:
        mock_observer_instance = MagicMock()
        mock_observer.return_value = mock_observer_instance

        result = await async_setup_observe(coordinator, hass, mock_config_entry)

        assert result is True
        assert mock_config_entry.runtime_data.observe_active is True
        mock_tap.clear_callbacks.assert_called_once()
        mock_tap._observation_manager.close.assert_awaited_once()
        mock_tap.observe.assert_awaited_once()
        mock_observer_instance.on_scene_update.assert_called_once_with(
            coordinator.data["scenes_all"]
        )


async def test_async_setup_observe_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tap: AsyncMock,
) -> None:
    """Test setting up CoAP observations with an error."""

    mock_config_entry.runtime_data = TewkeData(
        host="test_host",
        coordinator=AsyncMock(),
        tap=mock_tap,
        scenes={},
        pending_scenes={},
    )

    coordinator = AsyncMock()

    mock_tap.observe.side_effect = PyTewkeObserveError("test error")

    result = await async_setup_observe(coordinator, hass, mock_config_entry)

    assert result is False
    assert mock_config_entry.runtime_data.observe_active is False
    coordinator.reset_observation_timeout.assert_called_once()


async def test_tewke_observer(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test TewkeObserver callbacks."""

    mock_tap = AsyncMock()
    mock_tap.wall_dock_id = "test_dock_id"
    mock_config_entry.runtime_data = TewkeData(
        host="test_host",
        coordinator=AsyncMock(),
        tap=mock_tap,
        scenes={
            "scene1": Scene(id="scene1", name="Scene 1", isActive=False, brightness=0),
            "scene2": Scene(id="scene2", name="Scene 2", isActive=False, brightness=0),
        },
        pending_scenes={
            "pending1": Scene(
                id="pending1", name="Scene pending 1", isActive=False, brightness=0
            )
        },
    )
    mock_config_entry.add_to_hass(hass)

    coordinator = AsyncMock()
    coordinator.data = TewkeCoordinatorData(
        config=ConfigData.model_construct(),
        energy=None,
        radar=None,
        sensors=None,
        scenes={"scene1": Scene.model_construct(id="scene1", name="Scene 1")},
        scenes_all={"scene1": Scene.model_construct(id="scene1", name="Scene 1")},
        targets={},
    )

    observer = _TewkeObserver(coordinator, hass, mock_config_entry)

    # Test on_scene_update: deleted scene
    observer.on_scene_update(
        {"scene1": Scene.model_construct(id="scene1", name="Scene 1")}
    )
    assert "scene2" not in mock_config_entry.runtime_data.scenes

    # Test on_scene_update: new scene
    observer.on_scene_update(
        {
            "scene1": Scene.model_construct(id="scene1", name="Scene 1"),
            "scene3": Scene.model_construct(id="scene3", name="Scene 3"),
        }
    )
    assert "scene3" in mock_config_entry.runtime_data.pending_scenes

    # Test on_scene_update: no new scenes
    observer.on_scene_update(
        {"scene1": Scene.model_construct(id="scene1", name="Scene 1")}
    )
    assert "scene3" not in mock_config_entry.runtime_data.pending_scenes

    # Test on_target_update
    observer.on_target_update({1: Target.model_construct(id=1, name="Target 1")})
    assert coordinator.async_set_updated_data.call_count > 0

    # Test on_sensor_update
    observer.on_sensor_update(SensorData.model_construct())

    # Test on_radar_update
    observer.on_radar_update(RadarData.model_construct())

    # Test on_energy_update
    observer.on_energy_update(EnergyData.model_construct())

    # Test on_config_update: renaming
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "test_dock_id")},
        name="Old Name",
        sw_version="1.0.0",
    )

    observer.on_config_update(
        ConfigData.model_construct(device_name="New Name", tewke_os_version="1.1.0")
    )

    device = dev_reg.async_get(device.id)
    assert device.name == "New Name"
    assert device.sw_version == "1.1.0"
    assert mock_config_entry.data[CONF_NAME] == "New Name"
    assert mock_config_entry.title == "New Name"
