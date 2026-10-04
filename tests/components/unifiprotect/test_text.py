"""Test the UniFi Protect text platform."""

from unittest.mock import AsyncMock, patch

import pytest
from uiprotect.data import Camera, DoorbellMessageType, LCDMessage
from uiprotect.data.public_devices import PublicLcdMessage

from homeassistant.components.unifiprotect.const import DEFAULT_ATTRIBUTION
from homeassistant.components.unifiprotect.text import CAMERA
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .utils import (
    MockUFPFixture,
    adopt_devices,
    assert_entity_counts,
    ids_from_device_description,
    init_entry,
    make_public_camera,
    public_device_ws_message,
    remove_entities,
    setup_public_camera,
)


async def test_text_camera_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera, unadopted_camera: Camera
) -> None:
    """Test removing and re-adding a camera device."""

    ufp.api.bootstrap.nvr.system_info.ustorage = None
    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.TEXT, 1, 1)
    await remove_entities(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.TEXT, 0, 0)
    await adopt_devices(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.TEXT, 1, 1)


async def test_text_camera_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """Test text entity setup for camera devices."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.TEXT, 1, 1)

    description = CAMERA[0]
    unique_id, entity_id = await ids_from_device_description(
        hass, Platform.TEXT, doorbell, description
    )

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "Welcome"
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_text_camera_set(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Test text entity setting value camera devices."""

    setup_public_camera(ufp)
    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.TEXT, 1, 1)

    description = CAMERA[0]
    _unique_id, entity_id = await ids_from_device_description(
        hass, Platform.TEXT, doorbell, description
    )

    public = make_public_camera(doorbell)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    with patch.object(public, "set_lcd_message", new_callable=AsyncMock) as mock_method:
        await hass.services.async_call(
            "text",
            "set_value",
            {ATTR_ENTITY_ID: entity_id, "value": "Test test"},
            blocking=True,
        )

        mock_method.assert_called_once_with(
            DoorbellMessageType.CUSTOM_MESSAGE, text="Test test", reset_at=None
        )


@pytest.mark.parametrize(
    ("lcd_message", "expected"),
    [
        pytest.param(None, "Welcome", id="no_message"),
        pytest.param(
            PublicLcdMessage(type=DoorbellMessageType.CUSTOM_MESSAGE, text="Hi"),
            "Hi",
            id="custom",
        ),
        pytest.param(
            PublicLcdMessage(type=DoorbellMessageType.DO_NOT_DISTURB),
            "DO NOT DISTURB",
            id="unifi_message",
        ),
        pytest.param(PublicLcdMessage(), "Welcome", id="no_type"),
    ],
)
async def test_text_camera_reads_public(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    lcd_message: PublicLcdMessage | None,
    expected: str,
) -> None:
    """Test the doorbell text reads the public LCD message, not the private one."""

    doorbell.lcd_message = LCDMessage(
        type=DoorbellMessageType.CUSTOM_MESSAGE, text="Private"
    )
    setup_public_camera(ufp)
    await init_entry(hass, ufp, [doorbell])

    _, entity_id = await ids_from_device_description(
        hass, Platform.TEXT, doorbell, CAMERA[0]
    )
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "Welcome"

    public = make_public_camera(doorbell, lcd_message=lcd_message)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == expected
