"""Test the UniFi Protect button platform."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from uiprotect.data import Sensor
from uiprotect.data.devices import Camera, Chime
from uiprotect.data.public_devices import SensorFeatureCapability

from homeassistant.components.unifiprotect.button import SENSOR_BUTTONS
from homeassistant.components.unifiprotect.const import DEFAULT_ATTRIBUTION, DOMAIN
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .utils import (
    MockUFPFixture,
    adopt_devices,
    assert_entity_counts,
    enable_entity,
    ids_from_device_description,
    init_entry,
    remove_entities,
    setup_public_sensor,
)


async def test_button_chime_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, chime: Chime
) -> None:
    """Test removing and re-adding a light device."""

    await init_entry(hass, ufp, [chime])
    assert_entity_counts(hass, Platform.BUTTON, 4, 2)
    await remove_entities(hass, ufp, [chime])
    assert_entity_counts(hass, Platform.BUTTON, 0, 0)
    await adopt_devices(hass, ufp, [chime])
    assert_entity_counts(hass, Platform.BUTTON, 4, 2)


@pytest.mark.parametrize(
    ("unique_id_suffix", "entity_id", "api_method", "is_disabled"),
    [
        ("reboot", "button.test_chime_restart", "reboot_device", True),
        ("play", "button.test_chime_play_chime", "play_speaker", False),
    ],
)
async def test_chime_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    chime: Chime,
    unique_id_suffix: str,
    entity_id: str,
    api_method: str,
    is_disabled: bool,
) -> None:
    """Test chime button entities."""
    await init_entry(hass, ufp, [chime])
    assert_entity_counts(hass, Platform.BUTTON, 4, 2)

    unique_id = f"{chime.mac}_{unique_id_suffix}"

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.disabled is is_disabled
    assert entity.unique_id == unique_id

    if is_disabled:
        await enable_entity(hass, ufp.entry.entry_id, entity_id)

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    with patch.object(ufp.api, api_method, AsyncMock()) as mock_api_method:
        await hass.services.async_call(
            "button", "press", {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_api_method.assert_called_once()


async def test_adopt_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    chime: Chime,
    doorbell: Camera,
) -> None:
    """Test button entity."""

    chime._api = ufp.api
    chime.is_adopted = False
    chime.can_adopt = True

    await init_entry(hass, ufp, [])

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.old_obj = None
    mock_msg.new_obj = chime
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.BUTTON, 1, 1)

    ufp.api.adopt_device = AsyncMock()

    unique_id = f"{chime.mac}_adopt"
    entity_id = "button.test_chime_adopt_device"

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert not entity.disabled
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION

    await hass.services.async_call(
        "button", "press", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    ufp.api.adopt_device.assert_called_once()


async def test_adopt_button_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    chime: Chime,
    doorbell: Camera,
) -> None:
    """Test button entity."""

    entity_id = "button.test_chime_adopt_device"

    chime._api = ufp.api
    chime.is_adopted = False
    chime.can_adopt = True

    await init_entry(hass, ufp, [chime])
    assert_entity_counts(hass, Platform.BUTTON, 1, 1)
    entity = entity_registry.async_get(entity_id)
    assert entity

    await adopt_devices(hass, ufp, [chime], fully_adopt=True)
    assert_entity_counts(hass, Platform.BUTTON, 4, 2)
    entity = entity_registry.async_get(entity_id)
    assert entity is None


CLEAR_TAMPER = next(d for d in SENSOR_BUTTONS if d.key == "clear_tamper")


async def test_button_sense_capability_creation_filter(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """The clear-tamper button is only created for a sensor advertising tampering."""
    setup_public_sensor(ufp, capabilities={SensorFeatureCapability.TEMPERATURE})
    await init_entry(hass, ufp, [sensor_all])

    _, entity_id = await ids_from_device_description(
        hass, Platform.BUTTON, sensor_all, CLEAR_TAMPER
    )
    assert entity_registry.async_get(entity_id) is None


async def test_button_sense_capability_registry_cleanup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """A console upgrade removes the clear-tamper button when unsupported."""
    stale = entity_registry.async_get_or_create(
        Platform.BUTTON,
        DOMAIN,
        f"{sensor_all.mac}_{CLEAR_TAMPER.key}",
        config_entry=ufp.entry,
    )
    setup_public_sensor(ufp, capabilities={SensorFeatureCapability.TEMPERATURE})
    await init_entry(hass, ufp, [sensor_all], regenerate_ids=False)

    assert entity_registry.async_get(stale.entity_id) is None


async def test_button_sense_no_capability_map_creates_clear_tamper(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    sensor_all: Sensor,
) -> None:
    """Without a capability map (Protect below 7.2) the button is still created."""
    setup_public_sensor(ufp)
    await init_entry(hass, ufp, [sensor_all])

    _, entity_id = await ids_from_device_description(
        hass, Platform.BUTTON, sensor_all, CLEAR_TAMPER
    )
    assert entity_registry.async_get(entity_id) is not None
