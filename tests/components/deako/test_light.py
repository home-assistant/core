"""Tests for the light module."""
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.deako.const import DOMAIN
from homeassistant.components.deako.light import async_setup_entry
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MockDeakoDevices

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("init_integration")
@pytest.mark.asyncio
async def test_light_setup_no_devices(
    hass: HomeAssistant,
    pydeako_deako_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test light platform setup with no devices returned."""

    # no devices
    pydeako_deako_mock.get_devices.return_value = {}

    light_entities = []

    async def mock_add_entities(entities):
        for entity in entities:
            light_entities.append(entity)

    await async_setup_entry(hass, mock_config_entry, mock_add_entities)

    assert len(light_entities) == 0  # none have been added
    pydeako_deako_mock.disconnect.assert_called_once()


@pytest.mark.usefixtures("init_integration")
@pytest.mark.asyncio
async def test_light_setup_with_devices(
    hass: HomeAssistant,
    pydeako_deako_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test light platform setup with devices returned."""

    pydeako_deako_mock.get_devices.return_value = {
        "some_device": {},
    }

    light_entities = []

    def mock_add_entities(entities):
        for entity in entities:
            light_entities.append(entity)

    await async_setup_entry(hass, mock_config_entry, mock_add_entities)

    assert len(light_entities) == 1
    pydeako_deako_mock.set_state_callback.assert_called_once_with(
        "some_device", light_entities[0].on_update
    )


@pytest.mark.parametrize(("device_name", "device_uuid"), MockDeakoDevices().get_names())
@pytest.mark.usefixtures("mock_deako_devices", "init_integration")
@pytest.mark.asyncio
async def test_light_initial_props(
    hass: HomeAssistant,
    pydeako_deako_mock: MagicMock,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_devices: MockDeakoDevices,
    device_name: str,
    device_uuid: str,
) -> None:
    """Test lights are setup with accurate initial properties."""
    # make sure our initial state exists
    assert (state := hass.states.get(f"{LIGHT_DOMAIN}.{device_name}"))
    assert (
        state.state == STATE_ON
        if mock_devices.get_state(device_uuid)["power"]
        else STATE_OFF
    )
    if mock_devices.get_state(device_uuid).get("dim") is not None:
        # test that internal dim of 0-100 gets converted properly
        assert (
            state.attributes.get(ATTR_BRIGHTNESS)
            == mock_devices.get_state(device_uuid)["convertedDim"]
        )

    # test other properties
    entity = entity_registry.async_get(f"{LIGHT_DOMAIN}.{device_name}")
    assert entity
    assert entity.unique_id == device_uuid
    assert entity.original_name is None
    if mock_devices.get_state(device_uuid).get("dim") is not None:
        assert ColorMode.BRIGHTNESS in entity.capabilities.get("supported_color_modes")
        assert state.attributes["color_mode"] == ColorMode.BRIGHTNESS
    else:
        assert ColorMode.ONOFF in entity.capabilities.get("supported_color_modes")

    # test ha device
    device = device_registry.async_get(entity.device_id)
    assert device
    assert (
        device.model == "dimmer"
        if mock_devices.get_state(device_uuid).get("dim") is not None
        else "smart"
    )
    assert device.manufacturer == "Deako"
    assert device.name == device_name
    assert (DOMAIN, device_uuid) in device.identifiers


@pytest.mark.parametrize(("device_name", "device_uuid"), MockDeakoDevices().get_names())
@pytest.mark.asyncio
async def test_light_initial_props_default_state(
    hass: HomeAssistant,
    pydeako_deako_mock: MagicMock,
    mock_devices: MockDeakoDevices,
    mock_config_entry: MockConfigEntry,
    device_name: str,
    device_uuid: str,
) -> None:
    """Test lights are setup with accurate initial properties if client fails somehow."""
    pydeako_deako_mock.return_value.get_devices.return_value = mock_devices.devices

    pydeako_deako_mock.return_value.get_name.side_effect = mock_devices.get_name
    pydeako_deako_mock.return_value.get_state.return_value = None

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    hass.data[DOMAIN][mock_config_entry.entry_id] = pydeako_deako_mock

    # make sure our initial state exists
    assert (state := hass.states.get(f"{LIGHT_DOMAIN}.{device_name}"))
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("mock_deako_devices", "init_integration")
@pytest.mark.asyncio
async def test_light_power_change_on(
    hass: HomeAssistant,
    pydeako_deako_mock: MagicMock,
    mock_devices: MockDeakoDevices,
) -> None:
    """Test turing on a deako device."""
    pydeako_deako_mock.reset_mock()
    device_name, device_uuid = mock_devices.get_names()[0]
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: f"light.{device_name}"},
        blocking=True,
    )

    pydeako_deako_mock.return_value.control_device.assert_called_once_with(
        device_uuid, True, None
    )


@pytest.mark.usefixtures("mock_deako_devices", "init_integration")
@pytest.mark.asyncio
async def test_light_power_change_off(
    hass: HomeAssistant,
    pydeako_deako_mock: MagicMock,
    mock_devices: MockDeakoDevices,
) -> None:
    """Test turing on a deako device."""
    pydeako_deako_mock.reset_mock()
    device_name, device_uuid = mock_devices.get_names()[0]
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: f"light.{device_name}"},
        blocking=True,
    )

    pydeako_deako_mock.return_value.control_device.assert_called_once_with(
        device_uuid,
        False,
        None,
    )


@pytest.mark.parametrize(
    ("dim_input", "expected_dim_value"),
    [
        (3, 1),
        (255, 100),
        (127, 50),
    ],
)
@pytest.mark.usefixtures("mock_deako_devices", "init_integration")
@pytest.mark.asyncio
async def test_light_brightness_change(
    hass: HomeAssistant,
    pydeako_deako_mock: MagicMock,
    mock_devices: MockDeakoDevices,
    dim_input: int,
    expected_dim_value: int,
) -> None:
    """Test turing on a deako device."""
    device_name, device_uuid = mock_devices.get_names()[1]

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: f"light.{device_name}",
            ATTR_BRIGHTNESS: dim_input,
        },
        blocking=True,
    )

    pydeako_deako_mock.return_value.control_device.assert_called_once_with(
        device_uuid, True, expected_dim_value
    )


@pytest.mark.asyncio
async def test_light_on_update(
    hass: HomeAssistant,
    pydeako_deako_mock: MagicMock,
    mock_devices: MockDeakoDevices,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test lights are setup with accurate initial properties if client fails somehow."""
    pydeako_deako_mock.return_value.get_devices.return_value = mock_devices.devices

    pydeako_deako_mock.return_value.get_name.side_effect = mock_devices.get_name
    pydeako_deako_mock.return_value.get_state.side_effect = mock_devices.get_state

    callbacks = {}

    def set_state_callback(uuid: str, on_update):
        callbacks[uuid] = on_update

    pydeako_deako_mock.return_value.set_state_callback.side_effect = set_state_callback

    with patch(
        "homeassistant.components.deako.light.DeakoLightEntity.schedule_update_ha_state"
    ) as update_mock:
        mock_config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        hass.data[DOMAIN][mock_config_entry.entry_id] = pydeako_deako_mock

        pydeako_deako_mock.return_value.set_state_callback.assert_called()

        assert len(callbacks) == len(mock_devices.devices)
        for _key, callback in callbacks.items():
            callback()
            update_mock.assert_called_once()
            update_mock.reset_mock()
