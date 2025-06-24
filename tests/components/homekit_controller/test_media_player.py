"""Basic checks for HomeKit motion sensors and contact sensors."""

from collections.abc import Callable

from aiohomekit.model import Accessory
from aiohomekit.model.characteristics import (
    CharacteristicPermissions,
    CharacteristicsTypes,
)
from aiohomekit.model.services import Service, ServicesTypes
import pytest

from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_test_component


def create_tv_service(accessory: Accessory) -> Service:
    """Define tv characteristics.

    The TV is not currently documented publicly - this is based on observing really TV's that have HomeKit support.
    """
    tv_service = accessory.add_service(ServicesTypes.TELEVISION)

    tv_service.add_char(CharacteristicsTypes.ACTIVE, value=True)

    cur_state = tv_service.add_char(CharacteristicsTypes.CURRENT_MEDIA_STATE)
    cur_state.value = 0
    cur_state.perms.append(CharacteristicPermissions.events)

    remote = tv_service.add_char(CharacteristicsTypes.REMOTE_KEY)
    remote.value = None
    remote.perms.append(CharacteristicPermissions.paired_write)
    remote.perms.append(CharacteristicPermissions.events)

    # Add a HDMI 1 channel
    input_source_1 = accessory.add_service(ServicesTypes.INPUT_SOURCE)
    input_source_1.add_char(CharacteristicsTypes.IDENTIFIER, value=1)
    input_source_1.add_char(CharacteristicsTypes.CONFIGURED_NAME, value="HDMI 1")
    tv_service.add_linked_service(input_source_1)

    # Add a HDMI 2 channel
    input_source_2 = accessory.add_service(ServicesTypes.INPUT_SOURCE)
    input_source_2.add_char(CharacteristicsTypes.IDENTIFIER, value=2)
    input_source_2.add_char(CharacteristicsTypes.CONFIGURED_NAME, value="HDMI 2")
    tv_service.add_linked_service(input_source_2)

    # Support switching channels
    active_identifier = tv_service.add_char(CharacteristicsTypes.ACTIVE_IDENTIFIER)
    active_identifier.value = 1
    active_identifier.perms.append(CharacteristicPermissions.paired_write)

    return tv_service


def create_tv_service_with_target_media_state(accessory: Accessory) -> Service:
    """Define a TV service that can play/pause/stop without generate remote events."""
    service = create_tv_service(accessory)

    tms = service.add_char(CharacteristicsTypes.TARGET_MEDIA_STATE)
    tms.value = None
    tms.perms.append(CharacteristicPermissions.paired_write)

    return service


async def test_tv_read_state(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that we can read the state of a HomeKit fan accessory."""
    helper = await setup_test_component(hass, get_next_aid(), create_tv_service)

    state = await helper.async_update(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.CURRENT_MEDIA_STATE: 0,
        },
    )
    assert state.state == "playing"

    state = await helper.async_update(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.CURRENT_MEDIA_STATE: 1,
        },
    )
    assert state.state == "paused"

    state = await helper.async_update(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.CURRENT_MEDIA_STATE: 2,
        },
    )
    assert state.state == "idle"


async def test_tv_read_sources(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that we can read the input source of a HomeKit TV."""
    helper = await setup_test_component(hass, get_next_aid(), create_tv_service)

    state = await helper.poll_and_get_state()
    assert state.attributes["source"] == "HDMI 1"
    assert state.attributes["source_list"] == ["HDMI 1", "HDMI 2"]


async def test_play_remote_key(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that we can play media on a media player."""
    helper = await setup_test_component(hass, get_next_aid(), create_tv_service)

    await helper.async_update(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.CURRENT_MEDIA_STATE: 1,
        },
    )

    await hass.services.async_call(
        "media_player",
        "media_play",
        {"entity_id": "media_player.testdevice"},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.REMOTE_KEY: 11,
        },
    )

    # Second time should be a no-op
    await helper.async_update(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.CURRENT_MEDIA_STATE: 0,
            CharacteristicsTypes.REMOTE_KEY: None,
        },
    )

    await hass.services.async_call(
        "media_player",
        "media_play",
        {"entity_id": "media_player.testdevice"},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.REMOTE_KEY: None,
        },
    )


async def test_pause_remote_key(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that we can pause a media player."""
    helper = await setup_test_component(hass, get_next_aid(), create_tv_service)

    await helper.async_update(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.CURRENT_MEDIA_STATE: 0,
        },
    )

    await hass.services.async_call(
        "media_player",
        "media_pause",
        {"entity_id": "media_player.testdevice"},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.REMOTE_KEY: 11,
        },
    )

    # Second time should be a no-op
    await helper.async_update(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.CURRENT_MEDIA_STATE: 1,
            CharacteristicsTypes.REMOTE_KEY: None,
        },
    )

    await hass.services.async_call(
        "media_player",
        "media_pause",
        {"entity_id": "media_player.testdevice"},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.REMOTE_KEY: None,
        },
    )


async def test_play(hass: HomeAssistant, get_next_aid: Callable[[], int]) -> None:
    """Test that we can play media on a media player."""
    helper = await setup_test_component(
        hass, get_next_aid(), create_tv_service_with_target_media_state
    )

    await helper.async_update(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.CURRENT_MEDIA_STATE: 1,
        },
    )

    await hass.services.async_call(
        "media_player",
        "media_play",
        {"entity_id": "media_player.testdevice"},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.REMOTE_KEY: None,
            CharacteristicsTypes.TARGET_MEDIA_STATE: 0,
        },
    )

    # Second time should be a no-op
    await helper.async_update(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.CURRENT_MEDIA_STATE: 0,
            CharacteristicsTypes.TARGET_MEDIA_STATE: None,
        },
    )

    await hass.services.async_call(
        "media_player",
        "media_play",
        {"entity_id": "media_player.testdevice"},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.REMOTE_KEY: None,
            CharacteristicsTypes.TARGET_MEDIA_STATE: None,
        },
    )


async def test_pause(hass: HomeAssistant, get_next_aid: Callable[[], int]) -> None:
    """Test that we can turn pause a media player."""
    helper = await setup_test_component(
        hass, get_next_aid(), create_tv_service_with_target_media_state
    )

    await helper.async_update(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.CURRENT_MEDIA_STATE: 0,
        },
    )

    await hass.services.async_call(
        "media_player",
        "media_pause",
        {"entity_id": "media_player.testdevice"},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.REMOTE_KEY: None,
            CharacteristicsTypes.TARGET_MEDIA_STATE: 1,
        },
    )

    # Second time should be a no-op
    await helper.async_update(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.CURRENT_MEDIA_STATE: 1,
            CharacteristicsTypes.REMOTE_KEY: None,
        },
    )

    await hass.services.async_call(
        "media_player",
        "media_pause",
        {"entity_id": "media_player.testdevice"},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.REMOTE_KEY: None,
        },
    )


async def test_stop(hass: HomeAssistant, get_next_aid: Callable[[], int]) -> None:
    """Test that we can  stop a media player."""
    helper = await setup_test_component(
        hass, get_next_aid(), create_tv_service_with_target_media_state
    )

    await hass.services.async_call(
        "media_player",
        "media_stop",
        {"entity_id": "media_player.testdevice"},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.TARGET_MEDIA_STATE: 2,
        },
    )

    # Second time should be a no-op
    await helper.async_update(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.CURRENT_MEDIA_STATE: 2,
            CharacteristicsTypes.TARGET_MEDIA_STATE: None,
        },
    )

    await hass.services.async_call(
        "media_player",
        "media_stop",
        {"entity_id": "media_player.testdevice"},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.REMOTE_KEY: None,
            CharacteristicsTypes.TARGET_MEDIA_STATE: None,
        },
    )


async def test_tv_set_source(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that we can set the input source of a HomeKit TV."""
    helper = await setup_test_component(hass, get_next_aid(), create_tv_service)

    await hass.services.async_call(
        "media_player",
        "select_source",
        {"entity_id": "media_player.testdevice", "source": "HDMI 2"},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.ACTIVE_IDENTIFIER: 2,
        },
    )

    state = await helper.poll_and_get_state()
    assert state.attributes["source"] == "HDMI 2"


async def test_tv_set_source_fail(
    hass: HomeAssistant, get_next_aid: Callable[[], int]
) -> None:
    """Test that we can set the input source of a HomeKit TV."""
    helper = await setup_test_component(hass, get_next_aid(), create_tv_service)

    with pytest.raises(ValueError):
        await hass.services.async_call(
            "media_player",
            "select_source",
            {"entity_id": "media_player.testdevice", "source": "HDMI 999"},
            blocking=True,
        )

    state = await helper.poll_and_get_state()
    assert state.attributes["source"] == "HDMI 1"


async def test_migrate_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    get_next_aid: Callable[[], int],
) -> None:
    """Test a we can migrate a media_player unique id."""
    aid = get_next_aid()
    media_player_entry = entity_registry.async_get_or_create(
        "media_player",
        "homekit_controller",
        f"homekit-00:00:00:00:00:00-{aid}-8",
    )
    await setup_test_component(hass, aid, create_tv_service_with_target_media_state)

    assert (
        entity_registry.async_get(media_player_entry.entity_id).unique_id
        == f"00:00:00:00:00:00_{aid}_8"
    )


async def test_turn_on(hass: HomeAssistant, get_next_aid: Callable[[], int]) -> None:
    """Test that we can turn on a media player."""
    helper = await setup_test_component(
        hass, get_next_aid(), create_tv_service_with_target_media_state
    )

    await helper.async_update(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.CURRENT_MEDIA_STATE: 0,
        },
    )

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": "media_player.testdevice"},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.ACTIVE: 1,
        },
    )


async def test_turn_off(hass: HomeAssistant, get_next_aid: Callable[[], int]) -> None:
    """Test that we can turn off a media player."""
    helper = await setup_test_component(
        hass, get_next_aid(), create_tv_service_with_target_media_state
    )

    await helper.async_update(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.CURRENT_MEDIA_STATE: 0,
        },
    )

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_OFF,
        {"entity_id": "media_player.testdevice"},
        blocking=True,
    )
    helper.async_assert_service_values(
        ServicesTypes.TELEVISION,
        {
            CharacteristicsTypes.ACTIVE: 0,
        },
    )
