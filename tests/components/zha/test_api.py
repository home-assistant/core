"""Test ZHA API."""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
import zigpy.backups
import zigpy.state

from homeassistant.components import zha
from homeassistant.components.zha import api
from homeassistant.components.zha.core.const import RadioType
from homeassistant.components.zha.core.helpers import get_zha_gateway
from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from zigpy.application import ControllerApplication


@pytest.fixture(autouse=True)
def required_platform_only():
    """Only set up the required and required base platforms to speed up tests."""
    with patch("homeassistant.components.zha.PLATFORMS", ()):
        yield


async def test_async_get_network_settings_active(
    hass: HomeAssistant, setup_zha
) -> None:
    """Test reading settings with an active ZHA installation."""
    await setup_zha()

    settings = await api.async_get_network_settings(hass)
    assert settings.network_info.channel == 15


async def test_async_get_network_settings_inactive(
    hass: HomeAssistant, setup_zha, zigpy_app_controller: ControllerApplication
) -> None:
    """Test reading settings with an inactive ZHA installation."""
    await setup_zha()

    gateway = get_zha_gateway(hass)
    await zha.async_unload_entry(hass, gateway.config_entry)

    backup = zigpy.backups.NetworkBackup()
    backup.network_info.channel = 20
    zigpy_app_controller.backups.backups.append(backup)

    controller = AsyncMock()
    controller.SCHEMA = zigpy_app_controller.SCHEMA
    controller.new = AsyncMock(return_value=zigpy_app_controller)

    with patch.dict(
        "homeassistant.components.zha.core.const.RadioType._member_map_",
        ezsp=MagicMock(controller=controller, description="EZSP"),
    ):
        settings = await api.async_get_network_settings(hass)

    assert settings.network_info.channel == 20
    assert len(zigpy_app_controller.start_network.mock_calls) == 0


async def test_async_get_network_settings_missing(
    hass: HomeAssistant, setup_zha, zigpy_app_controller: ControllerApplication
) -> None:
    """Test reading settings with an inactive ZHA installation, no valid channel."""
    await setup_zha()

    gateway = get_zha_gateway(hass)
    await gateway.config_entry.async_unload(hass)

    # Network settings were never loaded for whatever reason
    zigpy_app_controller.state.network_info = zigpy.state.NetworkInfo()
    zigpy_app_controller.state.node_info = zigpy.state.NodeInfo()

    settings = await api.async_get_network_settings(hass)

    assert settings is None


async def test_async_get_network_settings_failure(hass: HomeAssistant) -> None:
    """Test reading settings with no ZHA config entries and no database."""
    with pytest.raises(ValueError):
        await api.async_get_network_settings(hass)


async def test_async_get_radio_type_active(hass: HomeAssistant, setup_zha) -> None:
    """Test reading the radio type with an active ZHA installation."""
    await setup_zha()

    radio_type = api.async_get_radio_type(hass)
    assert radio_type == RadioType.ezsp


async def test_async_get_radio_path_active(hass: HomeAssistant, setup_zha) -> None:
    """Test reading the radio path with an active ZHA installation."""
    await setup_zha()

    radio_path = api.async_get_radio_path(hass)
    assert radio_path == "/dev/ttyUSB0"


async def test_change_channel(
    hass: HomeAssistant, setup_zha, zigpy_app_controller: ControllerApplication
) -> None:
    """Test changing the channel."""
    await setup_zha()

    await api.async_change_channel(hass, 20)
    assert zigpy_app_controller.move_network_to_channel.mock_calls == [call(20)]


async def test_change_channel_auto(
    hass: HomeAssistant, setup_zha, zigpy_app_controller: ControllerApplication
) -> None:
    """Test changing the channel automatically using an energy scan."""
    await setup_zha()

    zigpy_app_controller.energy_scan.side_effect = None
    zigpy_app_controller.energy_scan.return_value = {c: c for c in range(11, 26 + 1)}

    with patch.object(api, "pick_optimal_channel", autospec=True, return_value=25):
        await api.async_change_channel(hass, "auto")

    assert zigpy_app_controller.move_network_to_channel.mock_calls == [call(25)]
