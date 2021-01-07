"""Tests for the integration of a twinly device."""

from typing import Tuple
from unittest.mock import patch

from homeassistant.components.twinkly.const import (
    CONF_ENTRY_HOST,
    CONF_ENTRY_ID,
    CONF_ENTRY_MODEL,
    CONF_ENTRY_NAME,
    DOMAIN as TWINKLY_DOMAIN,
)
from homeassistant.components.twinkly.light import TwinklyLight
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.entity_registry import RegistryEntry

from tests.common import MockConfigEntry
from tests.components.twinkly import (
    TEST_HOST,
    TEST_ID,
    TEST_MODEL,
    TEST_NAME_ORIGINAL,
    ClientMock,
)


async def test_missing_client(hass: HomeAssistant):
    """Validate that if client has not been setup, it fails immediately in setup."""
    try:
        config_entry = MockConfigEntry(
            data={
                CONF_ENTRY_HOST: TEST_HOST,
                CONF_ENTRY_ID: TEST_ID,
                CONF_ENTRY_NAME: TEST_NAME_ORIGINAL,
                CONF_ENTRY_MODEL: TEST_MODEL,
            }
        )
        TwinklyLight(config_entry, hass)
    except ValueError:
        return

    assert False


async def test_initial_state(hass: HomeAssistant):
    """Validate that entity and device states are updated on startup."""
    entity, device, _ = await _create_entries(hass)

    state = hass.states.get(entity.entity_id)

    # Basic state properties
    assert state.name == entity.unique_id
    assert state.state == "on"
    assert state.attributes["host"] == TEST_HOST
    assert state.attributes["brightness"] == 26
    assert state.attributes["friendly_name"] == entity.unique_id
    assert state.attributes["icon"] == "mdi:string-lights"

    # Validates that custom properties of the API device_info are propagated through attributes
    assert state.attributes["uuid"] == entity.unique_id

    assert entity.original_name == entity.unique_id
    assert entity.original_icon == "mdi:string-lights"

    assert device.name == entity.unique_id
    assert device.model == TEST_MODEL
    assert device.manufacturer == "LEDWORKS"


async def test_initial_state_offline(hass: HomeAssistant):
    """Validate that entity and device are restored from config is offline on startup."""
    client = ClientMock()
    client.is_offline = True
    entity, device, _ = await _create_entries(hass, client)

    state = hass.states.get(entity.entity_id)

    assert state.name == TEST_NAME_ORIGINAL
    assert state.state == "unavailable"
    assert state.attributes["friendly_name"] == TEST_NAME_ORIGINAL
    assert state.attributes["icon"] == "mdi:string-lights"

    assert entity.original_name == TEST_NAME_ORIGINAL
    assert entity.original_icon == "mdi:string-lights"

    assert device.name == TEST_NAME_ORIGINAL
    assert device.model == TEST_MODEL
    assert device.manufacturer == "LEDWORKS"


async def test_turn_on(hass: HomeAssistant):
    """Test support of the light.turn_on service."""
    client = ClientMock()
    client.is_on = False
    client.brightness = 20
    entity, _, _ = await _create_entries(hass, client)

    assert hass.states.get(entity.entity_id).state == "off"

    await hass.services.async_call(
        "light", "turn_on", service_data={"entity_id": entity.entity_id}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity.entity_id)

    assert state.state == "on"
    assert state.attributes["brightness"] == 51


async def test_turn_on_with_brightness(hass: HomeAssistant):
    """Test support of the light.turn_on service with a brightness parameter."""
    client = ClientMock()
    client.is_on = False
    client.brightness = 20
    entity, _, _ = await _create_entries(hass, client)

    assert hass.states.get(entity.entity_id).state == "off"

    await hass.services.async_call(
        "light",
        "turn_on",
        service_data={"entity_id": entity.entity_id, "brightness": 255},
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity.entity_id)

    assert state.state == "on"
    assert state.attributes["brightness"] == 255


async def test_turn_off(hass: HomeAssistant):
    """Test support of the light.turn_off service."""
    entity, _, _ = await _create_entries(hass)

    assert hass.states.get(entity.entity_id).state == "on"

    await hass.services.async_call(
        "light", "turn_off", service_data={"entity_id": entity.entity_id}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity.entity_id)

    assert state.state == "off"
    assert state.attributes["brightness"] == 0


async def test_update_name(hass: HomeAssistant):
    """
    Validate device's name update behavior.

    Validate that if device name is changed from the Twinkly app,
    then the name of the entity is updated and it's also persisted,
    so it can be restored when starting HA while Twinkly is offline.
    """
    entity, _, client = await _create_entries(hass)

    updated_config_entry = None

    async def on_update(ha, co):
        nonlocal updated_config_entry
        updated_config_entry = co

    hass.config_entries.async_get_entry(entity.unique_id).add_update_listener(on_update)

    client.change_name("new_device_name")
    await hass.services.async_call(
        "light", "turn_off", service_data={"entity_id": entity.entity_id}
    )  # We call turn_off which will automatically cause an async_update
    await hass.async_block_till_done()

    state = hass.states.get(entity.entity_id)

    assert updated_config_entry is not None
    assert updated_config_entry.data[CONF_ENTRY_NAME] == "new_device_name"
    assert state.attributes["friendly_name"] == "new_device_name"


async def test_unload(hass: HomeAssistant):
    """Validate that entities can be unloaded from the UI."""

    _, _, client = await _create_entries(hass)
    entry_id = client.id

    assert await hass.config_entries.async_unload(entry_id)


async def _create_entries(
    hass: HomeAssistant, client=None
) -> Tuple[RegistryEntry, DeviceEntry, ClientMock]:
    client = ClientMock() if client is None else client

    def get_client_mock(client, _):
        return client

    with patch("twinkly_client.TwinklyClient", side_effect=get_client_mock):
        config_entry = MockConfigEntry(
            domain=TWINKLY_DOMAIN,
            data={
                CONF_ENTRY_HOST: client,
                CONF_ENTRY_ID: client.id,
                CONF_ENTRY_NAME: TEST_NAME_ORIGINAL,
                CONF_ENTRY_MODEL: TEST_MODEL,
            },
            entry_id=client.id,
        )
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(client.id)
        await hass.async_block_till_done()

    device_registry = await hass.helpers.device_registry.async_get_registry()
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    entity_id = entity_registry.async_get_entity_id("light", TWINKLY_DOMAIN, client.id)
    entity = entity_registry.async_get(entity_id)
    device = device_registry.async_get_device({(TWINKLY_DOMAIN, client.id)}, set())

    assert entity is not None
    assert device is not None

    return entity, device, client
