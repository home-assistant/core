"""Tests for the light module."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pyvesync import VeSync
from pyvesync.base_devices.bulb_base import VeSyncBulb
from pyvesync.const import ProductTypes
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.vesync.const import DOMAIN
from homeassistant.components.vesync.services import VeSyncService
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import ALL_DEVICE_NAMES, mock_devices_response


@pytest.mark.parametrize("device_name", ALL_DEVICE_NAMES)
async def test_light_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    device_name: str,
) -> None:
    """Test the resulting setup state is as expected for the platform."""

    # Configure the API devices call for device_name
    mock_devices_response(aioclient_mock, device_name)

    # setup platform - only including the named device
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check device registry
    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert devices == snapshot(name="devices")

    # Check entity registry
    entities = [
        entity
        for entity in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entity.domain == LIGHT_DOMAIN
    ]
    assert entities == snapshot(name="entities")

    # Check states
    for entity in entities:
        assert hass.states.get(entity.entity_id) == snapshot(name=entity.entity_id)


async def _async_setup_bulb(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    manager: VeSync,
    entity_registry: er.EntityRegistry,
    bulb: Mock,
) -> str:
    """Set up the light platform with a single bulb and return its entity ID."""
    manager.devices.bulbs.append(bulb)

    with patch("homeassistant.components.vesync.PLATFORMS", [Platform.LIGHT]):
        await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(LIGHT_DOMAIN, DOMAIN, bulb.cid)
    assert entity_id is not None
    return entity_id


async def test_tunable_light_turn_on(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    manager: VeSync,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test turning on a tunable bulb with color temperature and brightness."""
    bulb = Mock(
        VeSyncBulb,
        cid="tunable_bulb",
        device_type="ESL100CW",
        device_name="Tunable Bulb",
        product_type=ProductTypes.BULB,
        sub_device_no=None,
        current_firm_version="1.0.0",
        supports_color_temp=True,
        supports_brightness=True,
        state=SimpleNamespace(
            connection_status="online",
            device_status="off",
            brightness=75,
            color_temp=50,
        ),
        set_color_temp=AsyncMock(),
        set_brightness=AsyncMock(),
        turn_on=AsyncMock(),
        turn_off=AsyncMock(),
    )
    entity_id = await _async_setup_bulb(
        hass, config_entry, manager, entity_registry, bulb
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_COLOR_TEMP_KELVIN: 6500,
            ATTR_BRIGHTNESS: 128,
        },
        blocking=True,
    )
    bulb.set_color_temp.assert_awaited_once_with(100)
    bulb.set_brightness.assert_awaited_once_with(50)
    bulb.turn_on.assert_not_awaited()


async def test_dimmable_light_turn_on_and_off(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    manager: VeSync,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a dimmable bulb through the light services."""
    bulb = Mock(
        VeSyncBulb,
        cid="dimmable_bulb",
        device_type="ESL100",
        device_name="Dimmable Bulb",
        product_type=ProductTypes.BULB,
        sub_device_no=None,
        current_firm_version="1.0.0",
        supports_color_temp=False,
        supports_brightness=True,
        state=SimpleNamespace(
            connection_status="online",
            device_status="on",
            brightness=None,
            color_temp=None,
        ),
        set_brightness=AsyncMock(),
        turn_on=AsyncMock(),
        turn_off=AsyncMock(),
    )
    entity_id = await _async_setup_bulb(
        hass, config_entry, manager, entity_registry, bulb
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ATTR_BRIGHTNESS] == 0

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 1},
        blocking=True,
    )
    bulb.set_brightness.assert_awaited_once_with(1)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    bulb.turn_on.assert_awaited_once_with()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    bulb.turn_off.assert_awaited_once_with()


async def _async_setup_rgb_nightlight(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    manager: VeSync,
    entity_registry: er.EntityRegistry,
    rgb_humidifier: Mock,
) -> str:
    """Set up the light platform with a humidifier night light."""
    manager.devices.humidifiers.append(rgb_humidifier)
    with patch("homeassistant.components.vesync.PLATFORMS", [Platform.LIGHT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = entity_registry.async_get_entity_id(
        LIGHT_DOMAIN, DOMAIN, f"{rgb_humidifier.cid}-nightlight"
    )
    assert entity_id is not None
    return entity_id


async def test_rgb_nightlight_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    manager: VeSync,
    entity_registry: er.EntityRegistry,
    rgb_humidifier: Mock,
) -> None:
    """Test the light's state, translated name, and existing unique ID."""
    entity_id = await _async_setup_rgb_nightlight(
        hass, config_entry, manager, entity_registry, rgb_humidifier
    )
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_FRIENDLY_NAME] == "OasisMist Night light"
    assert state.attributes[ATTR_RGB_COLOR] == (255, 0, 64)
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.unique_id == "rgb-humidifier-nightlight"
    assert entry.translation_key == "nightlight"


@pytest.mark.parametrize(
    ("native_brightness", "expected_brightness"),
    [
        pytest.param(40, 4, id="minimum"),
        pytest.param(70, 130, id="middle"),
        pytest.param(100, 255, id="maximum"),
        pytest.param(None, None, id="unknown"),
    ],
)
async def test_rgb_nightlight_brightness(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    manager: VeSync,
    entity_registry: er.EntityRegistry,
    rgb_humidifier: Mock,
    native_brightness: int | None,
    expected_brightness: int | None,
) -> None:
    """Test the native minimum remains an on-state brightness."""
    rgb_humidifier.state.rgb_nightlight_brightness = native_brightness
    entity_id = await _async_setup_rgb_nightlight(
        hass, config_entry, manager, entity_registry, rgb_humidifier
    )
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == expected_brightness


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        pytest.param({}, (None, None, None, None), id="restore"),
        pytest.param({ATTR_BRIGHTNESS: 1}, (40, None, None, None), id="minimum"),
        pytest.param({ATTR_BRIGHTNESS: 128}, (70, None, None, None), id="middle"),
        pytest.param({ATTR_BRIGHTNESS: 255}, (100, None, None, None), id="maximum"),
        pytest.param(
            {ATTR_RGB_COLOR: (0, 255, 64)},
            (None, 0, 255, 64),
            id="color",
        ),
        pytest.param(
            {ATTR_BRIGHTNESS: 128, ATTR_RGB_COLOR: (0, 255, 64)},
            (70, 0, 255, 64),
            id="brightness-and-color",
        ),
    ],
)
async def test_rgb_nightlight_turn_on(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    manager: VeSync,
    entity_registry: er.EntityRegistry,
    rgb_humidifier: Mock,
    data: dict[str, int | tuple[int, int, int]],
    expected: tuple[int | None, int | None, int | None, int | None],
) -> None:
    """Test service calls preserve omitted settings and convert brightness."""
    entity_id = await _async_setup_rgb_nightlight(
        hass, config_entry, manager, entity_registry, rgb_humidifier
    )
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, **data},
        blocking=True,
    )
    brightness, red, green, blue = expected
    rgb_humidifier.set_rgb_nightlight.assert_awaited_once_with(
        power=True, brightness=brightness, red=red, green=green, blue=blue
    )
    rgb_humidifier.turn_on.assert_not_called()


async def test_rgb_nightlight_turn_off(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    manager: VeSync,
    entity_registry: er.EntityRegistry,
    rgb_humidifier: Mock,
) -> None:
    """Test turning off only the night light."""
    entity_id = await _async_setup_rgb_nightlight(
        hass, config_entry, manager, entity_registry, rgb_humidifier
    )
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    rgb_humidifier.set_rgb_nightlight.assert_awaited_once_with(power=False)
    rgb_humidifier.turn_off.assert_not_called()


@pytest.mark.parametrize(
    ("data", "expected_brightness", "expected_color"),
    [
        pytest.param({}, 255, (255, 0, 64), id="power-only"),
        pytest.param({ATTR_BRIGHTNESS: 1}, 4, (255, 0, 64), id="minimum"),
        pytest.param({ATTR_BRIGHTNESS: 128}, 130, (255, 0, 64), id="middle"),
        pytest.param({ATTR_BRIGHTNESS: 255}, 255, (255, 0, 64), id="maximum"),
        pytest.param(
            {ATTR_RGB_COLOR: (0, 255, 64)}, 255, (0, 255, 64), id="color-only"
        ),
        pytest.param(
            {ATTR_BRIGHTNESS: 128, ATTR_RGB_COLOR: (0, 255, 64)},
            130,
            (0, 255, 64),
            id="brightness-and-color",
        ),
    ],
)
async def test_rgb_nightlight_commands_update_state(
    hass: HomeAssistant,
    rgb_humidifier_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    data: dict[str, int | tuple[int, int, int]],
    expected_brightness: int,
    expected_color: tuple[int, int, int],
) -> None:
    """Test real library commands update state and restore the light's settings."""
    entity_id = entity_registry.async_get_entity_id(
        LIGHT_DOMAIN, DOMAIN, "rgb-humidifier-nightlight"
    )
    assert entity_id is not None
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == STATE_OFF

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "https://smartapi.vesync.com/cloud/v2/deviceManaged/bypassV2",
        json={"code": 0, "result": {"code": 0}},
    )
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, **data},
        blocking=True,
    )
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == expected_brightness
    assert state.attributes[ATTR_RGB_COLOR] == expected_color

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == expected_brightness
    assert state.attributes[ATTR_RGB_COLOR] == expected_color
    device = rgb_humidifier_config_entry.runtime_data.manager.devices.humidifiers[0]
    assert device.state.device_status == STATE_OFF


@pytest.mark.parametrize("native_brightness", [40, 70, 100])
async def test_rgb_nightlight_restore_brightness(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    manager: VeSync,
    entity_registry: er.EntityRegistry,
    rgb_humidifier: Mock,
    native_brightness: int,
) -> None:
    """Test restoring the reported brightness preserves the native level."""
    rgb_humidifier.state.rgb_nightlight_brightness = native_brightness
    entity_id = await _async_setup_rgb_nightlight(
        hass, config_entry, manager, entity_registry, rgb_humidifier
    )
    assert (state := hass.states.get(entity_id)) is not None
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: state.attributes[ATTR_BRIGHTNESS]},
        blocking=True,
    )
    rgb_humidifier.set_rgb_nightlight.assert_awaited_once_with(
        power=True, brightness=native_brightness, red=None, green=None, blue=None
    )


@pytest.mark.parametrize("service", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
async def test_rgb_nightlight_command_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    manager: VeSync,
    entity_registry: er.EntityRegistry,
    rgb_humidifier: Mock,
    service: str,
) -> None:
    """Test failed library commands surface as translated service errors."""
    rgb_humidifier.set_rgb_nightlight.return_value = False
    rgb_humidifier.last_response = None
    entity_id = await _async_setup_rgb_nightlight(
        hass, config_entry, manager, entity_registry, rgb_humidifier
    )
    with pytest.raises(HomeAssistantError, match="Failed to control the night light"):
        await hass.services.async_call(
            LIGHT_DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )


@pytest.mark.parametrize(
    ("status", "connection", "expected"),
    [
        pytest.param("off", "online", STATE_OFF, id="off"),
        pytest.param(None, "online", STATE_UNAVAILABLE, id="unknown"),
        pytest.param("on", "offline", STATE_UNAVAILABLE, id="offline"),
    ],
)
async def test_rgb_nightlight_availability(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    manager: VeSync,
    entity_registry: er.EntityRegistry,
    rgb_humidifier: Mock,
    status: str | None,
    connection: str,
    expected: str,
) -> None:
    """Test power and availability independently of the humidifier power."""
    rgb_humidifier.state.rgb_nightlight_status = status
    rgb_humidifier.state.connection_status = connection
    entity_id = await _async_setup_rgb_nightlight(
        hass, config_entry, manager, entity_registry, rgb_humidifier
    )
    assert (state := hass.states.get(entity_id)) is not None
    assert state.state == expected


async def test_rgb_nightlight_discovery(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    manager: VeSync,
    entity_registry: er.EntityRegistry,
    rgb_humidifier: Mock,
) -> None:
    """Test discovering an RGB humidifier after initial setup."""
    with patch("homeassistant.components.vesync.PLATFORMS", [Platform.LIGHT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    manager.get_devices = AsyncMock(
        side_effect=lambda: manager.devices.humidifiers.append(rgb_humidifier)
    )
    await hass.services.async_call(
        DOMAIN, VeSyncService.UPDATE_DEVICES, {}, blocking=True
    )
    await hass.async_block_till_done()
    assert (
        entity_registry.async_get_entity_id(
            LIGHT_DOMAIN, DOMAIN, "rgb-humidifier-nightlight"
        )
        is not None
    )


async def test_humidifier_without_rgb_nightlight(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    manager: VeSync,
    entity_registry: er.EntityRegistry,
    rgb_humidifier: Mock,
) -> None:
    """Test humidifiers without RGB support do not create light entities."""
    rgb_humidifier.supports_rgb_nightlight = False
    manager.devices.humidifiers.append(rgb_humidifier)
    with patch("homeassistant.components.vesync.PLATFORMS", [Platform.LIGHT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert (
        entity_registry.async_get_entity_id(
            LIGHT_DOMAIN, DOMAIN, "rgb-humidifier-nightlight"
        )
        is None
    )
