"""Tests for home_connect image entities."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock

from aiohomeconnect.model import ArrayOfEvents, EventMessage, EventType, HomeAppliance
from aiohomeconnect.model.image import ArrayOfImages, Image
import pytest

from homeassistant.components.home_connect.const import DOMAIN
from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, EntityStateAttribute, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.IMAGE]


@pytest.fixture(autouse=True)
def images(client: MagicMock) -> list[Image]:
    """Fixture to inject and return the default image entities."""
    images = [
        Image(
            key="Refrigeration.Common.EnumType.Compartment.Type.InteriorRightRC",
            image_key="image_key_1",
            preview_image_key="preview_image_key_1",
            timestamp=1785974400000,
            quality="good",
        ),
        Image(
            key="Refrigeration.Common.EnumType.Compartment.Type.DoorRightRC",
            image_key="image_key_2",
            preview_image_key="preview_image_key_2",
            timestamp=1785974400000,
            quality="good",
        ),
    ]
    client.get_images = AsyncMock(return_value=ArrayOfImages(images))
    return images


@pytest.mark.parametrize("appliance", ["FridgeFreezer"], indirect=True)
async def test_paired_depaired_devices_flow(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    client: MagicMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test device removal and re-addition on API events."""
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, appliance.ha_id), config_entry.entry_id
    )
    assert device
    entity_entries = entity_registry.entities.get_entries_for_device_id(device.id)
    assert entity_entries

    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.DEPAIRED,
                data=ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, appliance.ha_id), config_entry.entry_id
    )
    assert not device
    for entity_entry in entity_entries:
        assert not entity_registry.async_get(entity_entry.entity_id)

    # Now that all everything related to the device is removed, pair it again
    await client.add_events(
        [
            EventMessage(
                appliance.ha_id,
                EventType.PAIRED,
                data=ArrayOfEvents([]),
            )
        ]
    )
    await hass.async_block_till_done()

    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, appliance.ha_id), config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_registry.async_get(entity_entry.entity_id)


@pytest.mark.parametrize("appliance", ["FridgeFreezer"], indirect=True)
async def test_image_functionality(
    hass: HomeAssistant,
    client: MagicMock,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test that the image entities use the correct image data."""
    image_data_dict = {
        "image_key_1": b"image_data_1",
        "image_key_2": b"image_data_2",
    }

    async def mock_get_image(_: str, *, image_key: str) -> bytes:
        return image_data_dict[image_key]

    client.get_image = AsyncMock(wraps=mock_get_image)

    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    client.get_images.assert_awaited_once_with(appliance.ha_id)
    assert client.get_image.await_count == 2
    for image_key in image_data_dict:
        client.get_image.assert_any_call(appliance.ha_id, image_key=image_key)

    _client = await hass_client()
    for entity_id, expected_image_data in (
        ("image.fridgefreezer_interior_right_camera", b"image_data_1"),
        ("image.fridgefreezer_door_right_camera", b"image_data_2"),
    ):
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "2026-08-06T00:00:00+00:00"

        resp = await _client.get(state.attributes[EntityStateAttribute.ENTITY_PICTURE])
        assert resp.status == 200
        assert await resp.read() == expected_image_data


@pytest.mark.parametrize("appliance", ["FridgeFreezer"], indirect=True)
async def test_update_image_entity_functionality(
    hass: HomeAssistant,
    client: MagicMock,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[MagicMock], Awaitable[bool]],
    appliance: HomeAppliance,
) -> None:
    """Test that the image update correctly.

    Whenever an entity does update, the integration update any other from the same
    appliance y there's an update available.
    """
    image_data_dict = {
        "image_key_1": b"image_data_1",
        "image_key_2": b"image_data_2",
        "image_key_3": b"image_data_3",
        "image_key_4": b"image_data_4",
    }
    entity_id = "image.fridgefreezer_interior_right_camera"

    async def mock_get_image(_: str, *, image_key: str) -> bytes:
        return image_data_dict[image_key]

    client.get_image = AsyncMock(wraps=mock_get_image)

    await async_setup_component(hass, HA_DOMAIN, {})
    assert await integration_setup(client)
    assert config_entry.state is ConfigEntryState.LOADED

    client.get_images.assert_awaited_once_with(appliance.ha_id)
    client.get_images.reset_mock()
    client.get_image.reset_mock()

    client.get_images.return_value.images.extend(
        [
            Image(
                key="Refrigeration.Common.EnumType.Compartment.Type.InteriorRightRC",
                image_key="image_key_3",
                preview_image_key="preview_image_key_3",
                timestamp=1785978000000,
                quality="good",
            ),
            Image(
                key="Refrigeration.Common.EnumType.Compartment.Type.DoorRightRC",
                image_key="image_key_4",
                preview_image_key="preview_image_key_4",
                timestamp=1785978000000,
                quality="good",
            ),
        ]
    )
    await hass.services.async_call(
        HA_DOMAIN, SERVICE_UPDATE_ENTITY, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    client.get_images.assert_awaited_once_with(appliance.ha_id)
    assert client.get_image.await_count == 2
    client.get_image.assert_any_await(appliance.ha_id, image_key="image_key_3")
    client.get_image.assert_any_await(appliance.ha_id, image_key="image_key_4")

    for entity_id, expected_image_data in (
        ("image.fridgefreezer_interior_right_camera", b"image_data_3"),
        ("image.fridgefreezer_door_right_camera", b"image_data_4"),
    ):
        state = hass.states.get(entity_id)
        assert state
        assert state.state == "2026-08-06T01:00:00+00:00"

        _client = await hass_client()
        resp = await _client.get(state.attributes[EntityStateAttribute.ENTITY_PICTURE])
        assert resp.status == 200
        assert await resp.read() == expected_image_data
