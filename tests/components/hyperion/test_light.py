"""Tests for the Hyperion integration."""
import pytest

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ATTR_EFFECT,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
)

from homeassistant.exceptions import PlatformNotReady

# from tests.async_mock import AsyncMock, MagicMock, patch
from asynctest import Mock, CoroutineMock, patch, call

from hyperion import const
from homeassistant.components.hyperion import light as hyperion_light

TEST_HOST = "test-hyperion-host"
TEST_NAME = "test-hyperion-name"
TEST_PRIORITY = 128

TEST_CONFIG = {
    CONF_HOST: TEST_HOST,
    CONF_NAME: TEST_NAME,
    CONF_PORT: const.DEFAULT_PORT,
    hyperion_light.CONF_PRIORITY: 128,
}


def create_mock_client():
    """Create a mock Hyperion client."""
    mock_client = Mock()
    mock_client.async_connect = CoroutineMock(return_value=True)
    mock_client.adjustment = None
    mock_client.effects = None
    return mock_client


def create_hyperion_entity(client=None):
    """Create a mock Hyperion entity."""
    entity = hyperion_light.Hyperion(
        TEST_NAME, TEST_PRIORITY, client or create_mock_client()
    )
    return entity


def create_client_and_entity():
    """Create a mock Hyperion client and entity."""
    client = create_mock_client()
    return client, create_hyperion_entity(client)


async def test_setup_platform(hass):
    """Test the platform setup."""
    add_entities = Mock()
    client = create_mock_client()

    with patch("hyperion.client.HyperionClient", return_value=client):
        await hyperion_light.async_setup_platform(hass, TEST_CONFIG, add_entities)
        await hass.async_block_till_done()

    # Make sure the background task is initiated.
    assert client.run.called

    # Make sure the entity is added.
    assert add_entities.called


async def test_setup_platform_not_ready(hass):
    """Test the platform not being ready."""
    add_entities = Mock()
    client = create_mock_client()
    client.async_connect = CoroutineMock(return_value=False)

    with pytest.raises(PlatformNotReady):
        with patch("hyperion.client.HyperionClient", return_value=client):
            await hyperion_light.async_setup_platform(hass, TEST_CONFIG, add_entities)
            await hass.async_block_till_done()

    # Make sure the background task is initiated.
    assert not client.run.called

    # Make sure the entity is added.
    assert not add_entities.called


async def test_light_basic_properies(hass):
    """Test the basic properties."""
    client, entity = create_client_and_entity()
    assert entity
    assert not entity.should_poll
    assert entity.name == TEST_NAME
    assert entity.brightness == 255
    assert entity.hs_color == (0.0, 0.0)

    client.is_on.return_value = False
    assert not entity.is_on

    client.is_on.return_value = True
    assert entity.is_on

    assert entity.icon == hyperion_light.ICON_LIGHTBULB
    assert entity.effect == hyperion_light.KEY_EFFECT_SOLID

    # By default the effect list is the 3 external sources + 'Solid'.
    assert len(entity.effect_list) == 4

    assert entity.supported_features == hyperion_light.SUPPORT_HYPERION

    client.is_connected = False
    assert not entity.available

    client.is_connected = True
    assert entity.available

    unique_id = "1234"
    client.id = unique_id
    assert entity.unique_id == unique_id


async def test_light_async_turn_on(hass):
    """Test turning the light on."""
    client, entity = create_client_and_entity()

    # On (=), 100% (=), solid (=), [255,255,255] (=)
    client.async_set_color = CoroutineMock(return_value=True)
    await entity.async_turn_on()
    assert client.async_set_color.call_args == call(
        **{
            const.KEY_PRIORITY: TEST_PRIORITY,
            const.KEY_COLOR: [255, 255, 255],
            const.KEY_ORIGIN: hyperion_light.DEFAULT_ORIGIN,
        }
    )

    # On (=), 50% (!), solid (=), [255,255,255] (=)
    # ===
    brightness = 128
    client.async_set_color = CoroutineMock(return_value=True)
    client.async_set_adjustment = CoroutineMock(return_value=True)
    await entity.async_turn_on(**{ATTR_BRIGHTNESS: brightness})
    assert client.async_set_adjustment.call_args == call(
        **{const.KEY_ADJUSTMENT: {const.KEY_BRIGHTNESS: 50}}
    )
    assert client.async_set_color.call_args == call(
        **{
            const.KEY_PRIORITY: TEST_PRIORITY,
            const.KEY_COLOR: [255, 255, 255],
            const.KEY_ORIGIN: hyperion_light.DEFAULT_ORIGIN,
        }
    )
    # Simulate a state callback from Hyperion.
    client.adjustment = [{const.KEY_BRIGHTNESS: 50}]
    entity._update_adjustment()
    assert entity.brightness == brightness

    # On (=), 50% (=), solid (=), [0,255,255] (!)
    hs_color = (180.0, 100.0)
    client.async_set_color = CoroutineMock(return_value=True)
    await entity.async_turn_on(**{ATTR_HS_COLOR: hs_color})
    assert client.async_set_color.call_args == call(
        **{
            const.KEY_PRIORITY: TEST_PRIORITY,
            const.KEY_COLOR: (0, 255, 255),
            const.KEY_ORIGIN: hyperion_light.DEFAULT_ORIGIN,
        }
    )
    # Simulate a state callback from Hyperion.
    client.visible_priority = {
        const.KEY_COMPONENTID: const.KEY_COMPONENTID_COLOR,
        const.KEY_VALUE: {const.KEY_RGB: (0, 255, 255)},
    }
    entity._update_priorities()
    assert entity.hs_color == hs_color
    assert entity.icon == hyperion_light.ICON_LIGHTBULB

    # On (=), 100% (!), solid, [0,255,255] (=)
    brightness = 255
    client.async_set_color = CoroutineMock(return_value=True)
    client.async_set_adjustment = CoroutineMock(return_value=True)
    await entity.async_turn_on(**{ATTR_BRIGHTNESS: brightness})
    assert client.async_set_adjustment.call_args == call(
        **{const.KEY_ADJUSTMENT: {const.KEY_BRIGHTNESS: 100}}
    )
    assert client.async_set_color.call_args == call(
        **{
            const.KEY_PRIORITY: TEST_PRIORITY,
            const.KEY_COLOR: (0, 255, 255),
            const.KEY_ORIGIN: hyperion_light.DEFAULT_ORIGIN,
        }
    )
    client.adjustment = [{const.KEY_BRIGHTNESS: 100}]
    entity._update_adjustment()
    assert entity.brightness == brightness

    # On (=), 100% (=), V4L (!), [0,255,255] (=)
    effect = const.KEY_COMPONENTID_EXTERNAL_SOURCES[2]  # V4L
    client.async_clear = CoroutineMock(return_value=True)
    client.async_set_component = CoroutineMock(return_value=True)
    await entity.async_turn_on(**{ATTR_EFFECT: effect})
    assert client.async_clear.call_args == call(**{const.KEY_PRIORITY: TEST_PRIORITY})
    assert client.async_set_component.call_args_list == [
        call(
            **{
                const.KEY_COMPONENTSTATE: {
                    const.KEY_COMPONENT: const.KEY_COMPONENTID_EXTERNAL_SOURCES[0],
                    const.KEY_STATE: False,
                }
            }
        ),
        call(
            **{
                const.KEY_COMPONENTSTATE: {
                    const.KEY_COMPONENT: const.KEY_COMPONENTID_EXTERNAL_SOURCES[1],
                    const.KEY_STATE: False,
                }
            }
        ),
        call(
            **{
                const.KEY_COMPONENTSTATE: {
                    const.KEY_COMPONENT: const.KEY_COMPONENTID_EXTERNAL_SOURCES[2],
                    const.KEY_STATE: True,
                }
            }
        ),
    ]
    client.visible_priority = {const.KEY_COMPONENTID: effect}
    entity._update_priorities()
    assert entity.icon == hyperion_light.ICON_EXTERNAL_SOURCE
    assert entity.effect == effect

    # On (=), 100% (=), "Warm Blobs" (!), [0,255,255] (=)
    effect = "Warm Blobs"
    client.async_clear = CoroutineMock(return_value=True)
    client.async_set_effect = CoroutineMock(return_value=True)
    await entity.async_turn_on(**{ATTR_EFFECT: effect})
    assert client.async_clear.call_args == call(**{const.KEY_PRIORITY: TEST_PRIORITY})
    assert client.async_set_effect.call_args == call(
        **{
            const.KEY_PRIORITY: TEST_PRIORITY,
            const.KEY_EFFECT: {const.KEY_NAME: effect},
            const.KEY_ORIGIN: hyperion_light.DEFAULT_ORIGIN,
        }
    )
    client.visible_priority = {
        const.KEY_COMPONENTID: const.KEY_COMPONENTID_EFFECT,
        const.KEY_OWNER: effect,
    }
    entity._update_priorities()
    assert entity.icon == hyperion_light.ICON_EFFECT
    assert entity.effect == effect

    # No calls if disconnected.
    client.is_connected = False
    client.async_clear = CoroutineMock(return_value=True)
    client.async_set_effect = CoroutineMock(return_value=True)
    await entity.async_turn_on()
    assert not client.async_clear.called
    assert not client.async_set_effect.called


async def test_light_async_turn_off(hass):
    """Test turning the light off."""
    client, entity = create_client_and_entity()

    client.async_set_component = CoroutineMock(return_value=True)
    await entity.async_turn_off()
    assert client.async_set_component.call_args == call(
        **{
            const.KEY_COMPONENTSTATE: {
                const.KEY_COMPONENT: const.KEY_COMPONENTID_LEDDEVICE,
                const.KEY_STATE: False,
            }
        }
    )

    # No calls if disconnected.
    client.is_connected = False
    client.async_set_component = CoroutineMock(return_value=True)
    await entity.async_turn_off()
    assert not client.async_set_component.called


async def test_light_async_updates_from_hyperion_client(hass):
    """Test receiving a variety of Hyperion client callbacks."""

    client, entity = create_client_and_entity()

    # State isn't saved without the hass attribute.
    entity.hass = Mock()

    # Bright change gets accepted.
    brightness = 10
    client.adjustment = [{const.KEY_BRIGHTNESS: brightness}]

    mock_update_ha_state = Mock()
    with patch(
        "homeassistant.components.hyperion.light.Hyperion.schedule_update_ha_state",
        new=mock_update_ha_state,
    ):
        entity._update_adjustment()
    assert entity.brightness == round(255 * (brightness / 100.0))
    assert mock_update_ha_state.call_count == 1

    # Broken brightness value is ignored.
    bad_brightness = -200
    client.adjustment = [{const.KEY_BRIGHTNESS: bad_brightness}]
    with patch(
        "homeassistant.components.hyperion.light.Hyperion.schedule_update_ha_state",
        new=mock_update_ha_state,
    ):
        entity._update_adjustment()
    assert entity.brightness == round(255 * (brightness / 100.0))
    assert mock_update_ha_state.call_count == 1

    # Update components.
    client.is_on.return_value = True
    assert entity.is_on
    client.is_on.return_value = False
    with patch(
        "homeassistant.components.hyperion.light.Hyperion.schedule_update_ha_state",
        new=mock_update_ha_state,
    ):
        entity._update_components()
    assert not entity.is_on
    assert mock_update_ha_state.call_count == 2

    # Update priorities (V4L)
    client.visible_priority = {const.KEY_COMPONENTID: const.KEY_COMPONENTID_V4L}

    with patch(
        "homeassistant.components.hyperion.light.Hyperion.schedule_update_ha_state",
        new=mock_update_ha_state,
    ):
        entity._update_priorities()
    assert entity.effect == const.KEY_COMPONENTID_V4L
    assert entity.icon == hyperion_light.ICON_EXTERNAL_SOURCE
    assert entity.hs_color == (0.0, 0.0)
    assert mock_update_ha_state.call_count == 3

    # Update priorities (Effect)
    effect = "foo"
    client.visible_priority = {
        const.KEY_COMPONENTID: const.KEY_COMPONENTID_EFFECT,
        const.KEY_OWNER: effect,
    }

    with patch(
        "homeassistant.components.hyperion.light.Hyperion.schedule_update_ha_state",
        new=mock_update_ha_state,
    ):
        entity._update_priorities()
    assert entity.effect == effect
    assert entity.icon == hyperion_light.ICON_EFFECT
    assert entity.hs_color == (0.0, 0.0)
    assert mock_update_ha_state.call_count == 4

    # Update priorities (Color)
    rgb = (0, 100, 100)
    client.visible_priority = {
        const.KEY_COMPONENTID: const.KEY_COMPONENTID_COLOR,
        const.KEY_VALUE: {const.KEY_RGB: rgb},
    }

    with patch(
        "homeassistant.components.hyperion.light.Hyperion.schedule_update_ha_state",
        new=mock_update_ha_state,
    ):
        entity._update_priorities()
    assert entity.effect == hyperion_light.KEY_EFFECT_SOLID
    assert entity.icon == hyperion_light.ICON_LIGHTBULB
    assert entity.hs_color == (180.0, 100.0)
    assert mock_update_ha_state.call_count == 5

    # Update effect list
    effects = [{const.KEY_NAME: "One"}, {const.KEY_NAME: "Two"}]
    client.effects = effects
    with patch(
        "homeassistant.components.hyperion.light.Hyperion.schedule_update_ha_state",
        new=mock_update_ha_state,
    ):
        entity._update_effect_list()
    assert entity.effect_list == [
        effect[const.KEY_NAME] for effect in effects
    ] + const.KEY_COMPONENTID_EXTERNAL_SOURCES + [hyperion_light.KEY_EFFECT_SOLID]
    assert mock_update_ha_state.call_count == 6

    # Update full state (should call all 3)
    client.adjustment = [{const.KEY_BRIGHTNESS: brightness}]
    client.visible_priority = {
        const.KEY_COMPONENTID: const.KEY_COMPONENTID_COLOR,
        const.KEY_VALUE: {const.KEY_RGB: rgb},
    }
    client.effects = effects

    with patch(
        "homeassistant.components.hyperion.light.Hyperion.schedule_update_ha_state",
        new=mock_update_ha_state,
    ):
        entity._update_full_state()
    assert mock_update_ha_state.call_count == 9
