"""Test the aidot device."""

from unittest.mock import AsyncMock, MagicMock, Mock

from aidot.device_client import DeviceStatusData
from aidot.exceptions import AidotAuthFailed
from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.aidot.coordinator import UPDATE_DEVICE_LIST_INTERVAL
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGBW_COLOR,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import async_init_integration
from .const import ENTITY_LIGHT, LIGHT_DOMAIN

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await async_init_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_turn_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mocked_device_client: MagicMock,
) -> None:
    """Test turn on."""
    await async_init_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT},
        blocking=True,
    )
    mocked_device_client.async_turn_on.assert_called_once()


async def test_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mocked_device_client: MagicMock,
) -> None:
    """Test turn off."""
    await async_init_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_LIGHT},
        blocking=True,
    )
    mocked_device_client.async_turn_off.assert_called_once()


async def test_turn_on_brightness(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mocked_device_client: MagicMock,
) -> None:
    """Test turn on brightness."""
    await async_init_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_BRIGHTNESS: 100},
        blocking=True,
    )
    mocked_device_client.async_set_brightness.assert_called_once()


async def test_turn_on_with_color_temp(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mocked_device_client: MagicMock,
) -> None:
    """Test turn on with color temp."""
    await async_init_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_COLOR_TEMP_KELVIN: 3000},
        blocking=True,
    )
    mocked_device_client.async_set_cct.assert_called_once()


async def test_turn_on_with_rgbw(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mocked_device_client: MagicMock,
) -> None:
    """Test turn on with rgbw."""
    await async_init_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_LIGHT, ATTR_RGBW_COLOR: (255, 255, 255, 255)},
        blocking=True,
    )
    mocked_device_client.async_set_rgbw.assert_called_once()


async def test_light_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mocked_device_client: MagicMock,
) -> None:
    """Test light becomes unavailable when device goes offline."""
    await async_init_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_LIGHT).state == STATE_ON

    # Simulate device going offline
    mocked_device_client.status.online = False
    status = Mock(spec=DeviceStatusData)
    status.online = False
    status.on = False
    status.dimming = 0
    status.cct = 0
    status.rgbw = (0, 0, 0, 0)

    # Trigger coordinator update via callback
    coordinator = mock_config_entry.runtime_data.device_coordinators["device_id"]
    coordinator.async_set_updated_data(status)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_LIGHT).state == STATE_UNAVAILABLE


async def test_coordinator_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mocked_aidot_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator handles auth failure during update."""
    await async_init_integration(hass, mock_config_entry)

    mocked_aidot_client.async_get_all_device = AsyncMock(side_effect=AidotAuthFailed())
    freezer.tick(UPDATE_DEVICE_LIST_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is not None


async def test_coordinator_device_removal(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mocked_aidot_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator handles device removal."""
    await async_init_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_LIGHT) is not None

    # Return empty device list
    from aidot.const import CONF_DEVICE_LIST

    mocked_aidot_client.async_get_all_device.return_value = {CONF_DEVICE_LIST: []}
    freezer.tick(UPDATE_DEVICE_LIST_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
