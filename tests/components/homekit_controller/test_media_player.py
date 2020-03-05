"""Basic checks for HomeKit motion sensors and contact sensors."""
from aiohomekit.model.characteristics import (
    CharacteristicPermissions,
    CharacteristicsTypes,
)
from aiohomekit.model.services import ServicesTypes

from tests.components.homekit_controller.common import setup_test_component

CURRENT_MEDIA_STATE = ("television", "current-media-state")
TARGET_MEDIA_STATE = ("television", "target-media-state")
REMOTE_KEY = ("television", "remote-key")


def create_tv_service(accessory):
    """
    Define tv characteristics.

    The TV is not currently documented publicly - this is based on observing really TV's that have HomeKit support.
    """
    service = accessory.add_service(ServicesTypes.TELEVISION)

    cur_state = service.add_char(CharacteristicsTypes.CURRENT_MEDIA_STATE)
    cur_state.value = 0

    remote = service.add_char(CharacteristicsTypes.REMOTE_KEY)
    remote.value = None
    remote.perms.append(CharacteristicPermissions.paired_write)

    return service


def create_tv_service_with_target_media_state(accessory):
    """Define a TV service that can play/pause/stop without generate remote events."""
    service = create_tv_service(accessory)

    tms = service.add_char(CharacteristicsTypes.TARGET_MEDIA_STATE)
    tms.value = None
    tms.perms.append(CharacteristicPermissions.paired_write)

    return service


async def test_tv_read_state(hass, utcnow):
    """Test that we can read the state of a HomeKit fan accessory."""
    helper = await setup_test_component(hass, create_tv_service)

    helper.characteristics[CURRENT_MEDIA_STATE].value = 0
    state = await helper.poll_and_get_state()
    assert state.state == "playing"

    helper.characteristics[CURRENT_MEDIA_STATE].value = 1
    state = await helper.poll_and_get_state()
    assert state.state == "paused"

    helper.characteristics[CURRENT_MEDIA_STATE].value = 2
    state = await helper.poll_and_get_state()
    assert state.state == "idle"


async def test_play_remote_key(hass, utcnow):
    """Test that we can play media on a media player."""
    helper = await setup_test_component(hass, create_tv_service)

    helper.characteristics[CURRENT_MEDIA_STATE].value = 1
    await helper.poll_and_get_state()

    await hass.services.async_call(
        "media_player",
        "media_play",
        {"entity_id": "media_player.testdevice"},
        blocking=True,
    )
    assert helper.characteristics[REMOTE_KEY].value == 11

    # Second time should be a no-op
    helper.characteristics[CURRENT_MEDIA_STATE].value = 0
    await helper.poll_and_get_state()

    helper.characteristics[REMOTE_KEY].value = None
    await hass.services.async_call(
        "media_player",
        "media_play",
        {"entity_id": "media_player.testdevice"},
        blocking=True,
    )
    assert helper.characteristics[REMOTE_KEY].value is None


async def test_pause_remote_key(hass, utcnow):
    """Test that we can pause a media player."""
    helper = await setup_test_component(hass, create_tv_service)

    helper.characteristics[CURRENT_MEDIA_STATE].value = 0
    await helper.poll_and_get_state()

    await hass.services.async_call(
        "media_player",
        "media_pause",
        {"entity_id": "media_player.testdevice"},
        blocking=True,
    )
    assert helper.characteristics[REMOTE_KEY].value == 11

    # Second time should be a no-op
    helper.characteristics[CURRENT_MEDIA_STATE].value = 1
    await helper.poll_and_get_state()

    helper.characteristics[REMOTE_KEY].value = None
    await hass.services.async_call(
        "media_player",
        "media_pause",
        {"entity_id": "media_player.testdevice"},
        blocking=True,
    )
    assert helper.characteristics[REMOTE_KEY].value is None


async def test_play(hass, utcnow):
    """Test that we can play media on a media player."""
    helper = await setup_test_component(hass, create_tv_service_with_target_media_state)

    helper.characteristics[CURRENT_MEDIA_STATE].value = 1
    await helper.poll_and_get_state()

    await hass.services.async_call(
        "media_player",
        "media_play",
        {"entity_id": "media_player.testdevice"},
        blocking=True,
    )
    assert helper.characteristics[REMOTE_KEY].value is None
    assert helper.characteristics[TARGET_MEDIA_STATE].value == 0

    # Second time should be a no-op
    helper.characteristics[CURRENT_MEDIA_STATE].value = 0
    await helper.poll_and_get_state()

    helper.characteristics[TARGET_MEDIA_STATE].value = None
    await hass.services.async_call(
        "media_player",
        "media_play",
        {"entity_id": "media_player.testdevice"},
        blocking=True,
    )
    assert helper.characteristics[REMOTE_KEY].value is None
    assert helper.characteristics[TARGET_MEDIA_STATE].value is None


async def test_pause(hass, utcnow):
    """Test that we can turn pause a media player."""
    helper = await setup_test_component(hass, create_tv_service_with_target_media_state)

    helper.characteristics[CURRENT_MEDIA_STATE].value = 0
    await helper.poll_and_get_state()

    await hass.services.async_call(
        "media_player",
        "media_pause",
        {"entity_id": "media_player.testdevice"},
        blocking=True,
    )
    assert helper.characteristics[REMOTE_KEY].value is None
    assert helper.characteristics[TARGET_MEDIA_STATE].value == 1

    # Second time should be a no-op
    helper.characteristics[CURRENT_MEDIA_STATE].value = 1
    await helper.poll_and_get_state()

    helper.characteristics[REMOTE_KEY].value = None
    await hass.services.async_call(
        "media_player",
        "media_pause",
        {"entity_id": "media_player.testdevice"},
        blocking=True,
    )
    assert helper.characteristics[REMOTE_KEY].value is None


async def test_stop(hass, utcnow):
    """Test that we can  stop a media player."""
    helper = await setup_test_component(hass, create_tv_service_with_target_media_state)

    await hass.services.async_call(
        "media_player",
        "media_stop",
        {"entity_id": "media_player.testdevice"},
        blocking=True,
    )
    assert helper.characteristics[TARGET_MEDIA_STATE].value == 2

    # Second time should be a no-op
    helper.characteristics[CURRENT_MEDIA_STATE].value = 2
    await helper.poll_and_get_state()

    helper.characteristics[TARGET_MEDIA_STATE].value = None
    await hass.services.async_call(
        "media_player",
        "media_stop",
        {"entity_id": "media_player.testdevice"},
        blocking=True,
    )
    assert helper.characteristics[REMOTE_KEY].value is None
    assert helper.characteristics[TARGET_MEDIA_STATE].value is None
