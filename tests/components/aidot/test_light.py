"""Test the aidot device."""

from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion

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
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import async_init_integration
from .const import (
    ENTITY_LIGHT,
    ENTITY_LIGHT2,
    LIGHT_DOMAIN,
    TEST_DEVICE_LIST,
    TEST_MULTI_DEVICE_LIST,
)

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


async def test_dynamic_device_add(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mocked_aidot_client: MagicMock,
) -> None:
    """Test if adding a new device dynamically creates the corresponding light entity."""
    await async_init_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_LIGHT2)
    assert state is None

    mocked_aidot_client.async_get_all_device.return_value = TEST_MULTI_DEVICE_LIST
    freezer.tick(UPDATE_DEVICE_LIST_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_LIGHT2)
    assert state


async def test_dynamic_device_remove(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mocked_aidot_client: MagicMock,
) -> None:
    """Test if adding a new device dynamically creates the corresponding light entity."""
    mocked_aidot_client.async_get_all_device = AsyncMock(
        return_value=TEST_MULTI_DEVICE_LIST
    )
    await async_init_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_LIGHT2)
    assert state
    mocked_aidot_client.async_get_all_device = AsyncMock(return_value=TEST_DEVICE_LIST)
    freezer.tick(UPDATE_DEVICE_LIST_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_LIGHT2)
    assert state is None
