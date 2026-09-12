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
from homeassistant.helpers import device_registry as dr, entity_registry as er

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
        coordinator=MagicMock(),
        tap=mock_tap,
    )

    coordinator = MagicMock()
    coordinator.data = {
        "scenes": {"scene1": Scene.model_construct(id="scene1", name="Scene 1")}  # type: ignore[call-arg]
    }

    mock_tap._observation_manager = AsyncMock()

    with patch("homeassistant.components.tewke.util._TewkeObserver") as mock_observer:
        mock_observer_instance = MagicMock()
        mock_observer.return_value = mock_observer_instance

        result = await async_setup_observe(coordinator, hass, mock_config_entry)

        assert result is True
        assert mock_config_entry.runtime_data.observe_active is True
        mock_tap.clear_callbacks.assert_called_once()
        mock_tap.close_observations.assert_awaited_once()
        mock_tap.observe.assert_awaited_once()


async def test_async_setup_observe_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tap: AsyncMock,
) -> None:
    """Test setting up CoAP observations with an error."""

    mock_config_entry.runtime_data = TewkeData(
        host="test_host",
        coordinator=MagicMock(),
        tap=mock_tap,
    )

    coordinator = MagicMock()

    mock_tap.observe.side_effect = PyTewkeObserveError("test error")

    result = await async_setup_observe(coordinator, hass, mock_config_entry)

    assert result is False
    assert mock_config_entry.runtime_data.observe_active is False
    coordinator.reset_observation_timeout.assert_called_once()


async def test_tewke_observer(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test TewkeObserver callbacks."""

    mock_tap = AsyncMock()
    mock_tap.wall_dock_id = "test_dock_id"
    mock_config_entry.runtime_data = TewkeData(
        host="test_host",
        coordinator=MagicMock(),
        tap=mock_tap,
    )
    mock_config_entry.add_to_hass(hass)

    coordinator = MagicMock()
    coordinator.data = TewkeCoordinatorData(
        config=ConfigData.model_construct(hardware_id="test_hardware"),  # type: ignore[call-arg]
        energy=None,
        energy_override=None,
        radar=None,
        sensors=None,
        scenes={
            "scene1": Scene.model_construct(id="scene1", name="Scene 1"),  # type: ignore[call-arg]
            "scene2": Scene.model_construct(id="scene2", name="Scene 2"),  # type: ignore[call-arg]
        },
        targets={},
    )

    def _mock_set_updated_data(data):
        coordinator.data = data

    coordinator.async_set_updated_data.side_effect = _mock_set_updated_data

    observer = _TewkeObserver(coordinator, hass, mock_config_entry)

    # Add scene2 to entity registry
    entity_registry.async_get_or_create(
        domain="light",
        platform=DOMAIN,
        unique_id="test_hardware_scene2",
    )
    assert entity_registry.async_get_entity_id("light", DOMAIN, "test_hardware_scene2")

    # Mock wall_dock_id as None to hit the early return
    mock_tap.wall_dock_id = None
    observer.on_config_update(
        ConfigData.model_construct(hardware_id="test_hardware")  # type: ignore[call-arg]
    )
    mock_tap.wall_dock_id = "test_dock_id"

    # Test on_scene_update: deleted scene
    observer.on_scene_update(
        {"scene1": Scene.model_construct(id="scene1", name="Scene 1")}  # type: ignore[call-arg]
    )
    assert "scene2" not in coordinator.data["scenes"]
    assert not entity_registry.async_get_entity_id(
        "light", DOMAIN, "test_hardware_scene2"
    )

    # Test on_scene_update: new scene
    with patch(
        "homeassistant.components.tewke.util.async_dispatcher_send"
    ) as mock_dispatcher:
        observer.on_scene_update(
            {
                "scene1": Scene.model_construct(id="scene1", name="Scene 1"),  # type: ignore[call-arg]
                "scene3": Scene.model_construct(id="scene3", name="Scene 3"),  # type: ignore[call-arg]
            }
        )
        assert "scene3" in coordinator.data["scenes"]
        mock_dispatcher.assert_called_once()
        assert (
            mock_dispatcher.call_args[0][1]
            == f"tewke_add_scenes_{mock_config_entry.entry_id}"
        )

    # Test on_scene_update: no new scenes
    observer.on_scene_update(
        {
            "scene1": Scene.model_construct(id="scene1", name="Scene 1"),  # type: ignore[call-arg]
            "scene3": Scene.model_construct(id="scene3", name="Scene 3"),  # type: ignore[call-arg]
        }
    )

    # Test on_target_update
    observer.on_target_update({1: Target.model_construct(id=1, name="Target 1")})  # type: ignore[call-arg]
    assert coordinator.async_set_updated_data.call_count > 0

    # Test on_sensor_update
    observer.on_sensor_update(SensorData.model_construct())  # type: ignore[call-arg]

    # Test on_radar_update
    observer.on_radar_update(RadarData.model_construct())  # type: ignore[call-arg]

    # Test on_energy_update
    observer.on_energy_update(EnergyData.model_construct())  # type: ignore[call-arg]

    # Test on_config_update: renaming
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "test_dock_id")},
        name="Old Name",
        sw_version="1.0.0",
    )

    observer.on_config_update(
        ConfigData.model_construct(device_name="New Name", tewke_os_version="1.1.0")  # type: ignore[call-arg]
    )

    assert device
    updated_device = device_registry.async_get(device.id)
    assert updated_device
    assert updated_device.name == "New Name"
    assert updated_device.sw_version == "1.1.0"
    assert mock_config_entry.data[CONF_NAME] == "New Name"
    assert mock_config_entry.title == "New Name"
