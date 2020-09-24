"""Tests for the Hyperion integration."""
# from tests.async_mock import AsyncMock, MagicMock, patch
from asynctest import CoroutineMock, Mock, call, patch
from hyperion import const

from homeassistant.components.hyperion import light as hyperion_light
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.setup import async_setup_component

TEST_HOST = "test-hyperion-host"
TEST_PORT = const.DEFAULT_PORT
TEST_NAME = "test_hyperion_name"
TEST_PRIORITY = 128
TEST_ENTITY_ID = f"{DOMAIN}.{TEST_NAME}"


def create_mock_client():
    """Create a mock Hyperion client."""
    mock_client = Mock()
    mock_client.async_client_connect = CoroutineMock(return_value=True)
    mock_client.adjustment = None
    mock_client.effects = None
    mock_client.id = "%s:%i" % (TEST_HOST, TEST_PORT)
    return mock_client


def call_registered_callback(client, key, *args, **kwargs):
    """Call a Hyperion entity callback that was registered with the client."""
    return client.set_callbacks.call_args[0][0][key](*args, **kwargs)


async def setup_entity(hass, client=None):
    """Add a test Hyperion entity to hass."""
    client = client or create_mock_client()
    with patch("hyperion.client.HyperionClient", return_value=client):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    "platform": "hyperion",
                    "name": TEST_NAME,
                    "host": TEST_HOST,
                    "port": const.DEFAULT_PORT,
                    "priority": TEST_PRIORITY,
                }
            },
        )
    await hass.async_block_till_done()


async def test_setup_platform(hass):
    """Test setting up the platform."""
    client = create_mock_client()
    await setup_entity(hass, client=client)
    assert hass.states.get(TEST_ENTITY_ID) is not None


async def test_setup_platform_not_ready(hass):
    """Test the platform not being ready."""
    client = create_mock_client()
    client.async_client_connect = CoroutineMock(return_value=False)

    await setup_entity(hass, client=client)
    assert hass.states.get(TEST_ENTITY_ID) is None


async def test_light_basic_properies(hass):
    """Test the basic properties."""
    client = create_mock_client()
    await setup_entity(hass, client=client)

    entity_state = hass.states.get(TEST_ENTITY_ID)
    assert entity_state.state == "on"
    assert entity_state.attributes["brightness"] == 255
    assert entity_state.attributes["hs_color"] == (0.0, 0.0)
    assert entity_state.attributes["icon"] == hyperion_light.ICON_LIGHTBULB
    assert entity_state.attributes["effect"] == hyperion_light.KEY_EFFECT_SOLID

    # By default the effect list is the 3 external sources + 'Solid'.
    assert len(entity_state.attributes["effect_list"]) == 4

    assert (
        entity_state.attributes["supported_features"] == hyperion_light.SUPPORT_HYPERION
    )


async def test_light_async_turn_on(hass):
    """Test turning the light on."""
    client = create_mock_client()
    await setup_entity(hass, client=client)

    # On (=), 100% (=), solid (=), [255,255,255] (=)
    client.async_send_set_color = CoroutineMock(return_value=True)
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: TEST_ENTITY_ID}, blocking=True
    )

    assert client.async_send_set_color.call_args == call(
        **{
            const.KEY_PRIORITY: TEST_PRIORITY,
            const.KEY_COLOR: [255, 255, 255],
            const.KEY_ORIGIN: hyperion_light.DEFAULT_ORIGIN,
        }
    )

    # On (=), 50% (!), solid (=), [255,255,255] (=)
    # ===
    brightness = 128
    client.async_send_set_color = CoroutineMock(return_value=True)
    client.async_send_set_adjustment = CoroutineMock(return_value=True)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID, ATTR_BRIGHTNESS: brightness},
        blocking=True,
    )

    assert client.async_send_set_adjustment.call_args == call(
        **{const.KEY_ADJUSTMENT: {const.KEY_BRIGHTNESS: 50}}
    )
    assert client.async_send_set_color.call_args == call(
        **{
            const.KEY_PRIORITY: TEST_PRIORITY,
            const.KEY_COLOR: [255, 255, 255],
            const.KEY_ORIGIN: hyperion_light.DEFAULT_ORIGIN,
        }
    )

    # Simulate a state callback from Hyperion.
    client.adjustment = [{const.KEY_BRIGHTNESS: 50}]
    call_registered_callback(client, "adjustment-update")
    entity_state = hass.states.get(TEST_ENTITY_ID)
    assert entity_state.state == "on"
    assert entity_state.attributes["brightness"] == brightness

    # On (=), 50% (=), solid (=), [0,255,255] (!)
    hs_color = (180.0, 100.0)
    client.async_send_set_color = CoroutineMock(return_value=True)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID, ATTR_HS_COLOR: hs_color},
        blocking=True,
    )

    assert client.async_send_set_color.call_args == call(
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

    call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_ENTITY_ID)
    assert entity_state.attributes["hs_color"] == hs_color
    assert entity_state.attributes["icon"] == hyperion_light.ICON_LIGHTBULB

    # On (=), 100% (!), solid, [0,255,255] (=)
    brightness = 255
    client.async_send_set_color = CoroutineMock(return_value=True)
    client.async_send_set_adjustment = CoroutineMock(return_value=True)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID, ATTR_BRIGHTNESS: brightness},
        blocking=True,
    )

    assert client.async_send_set_adjustment.call_args == call(
        **{const.KEY_ADJUSTMENT: {const.KEY_BRIGHTNESS: 100}}
    )
    assert client.async_send_set_color.call_args == call(
        **{
            const.KEY_PRIORITY: TEST_PRIORITY,
            const.KEY_COLOR: (0, 255, 255),
            const.KEY_ORIGIN: hyperion_light.DEFAULT_ORIGIN,
        }
    )
    client.adjustment = [{const.KEY_BRIGHTNESS: 100}]
    call_registered_callback(client, "adjustment-update")
    entity_state = hass.states.get(TEST_ENTITY_ID)
    assert entity_state.attributes["brightness"] == brightness

    # On (=), 100% (=), V4L (!), [0,255,255] (=)
    effect = const.KEY_COMPONENTID_EXTERNAL_SOURCES[2]  # V4L
    client.async_send_clear = CoroutineMock(return_value=True)
    client.async_send_set_component = CoroutineMock(return_value=True)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID, ATTR_EFFECT: effect},
        blocking=True,
    )

    assert client.async_send_clear.call_args == call(
        **{const.KEY_PRIORITY: TEST_PRIORITY}
    )
    assert client.async_send_set_component.call_args_list == [
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
    call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_ENTITY_ID)
    assert entity_state.attributes["icon"] == hyperion_light.ICON_EXTERNAL_SOURCE
    assert entity_state.attributes["effect"] == effect

    # On (=), 100% (=), "Warm Blobs" (!), [0,255,255] (=)
    effect = "Warm Blobs"
    client.async_send_clear = CoroutineMock(return_value=True)
    client.async_send_set_effect = CoroutineMock(return_value=True)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID, ATTR_EFFECT: effect},
        blocking=True,
    )

    assert client.async_send_clear.call_args == call(
        **{const.KEY_PRIORITY: TEST_PRIORITY}
    )
    assert client.async_send_set_effect.call_args == call(
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
    call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_ENTITY_ID)
    assert entity_state.attributes["icon"] == hyperion_light.ICON_EFFECT
    assert entity_state.attributes["effect"] == effect

    # No calls if disconnected.
    client.has_loaded_state = False
    call_registered_callback(client, "client-update", {"loaded-state": False})
    client.async_send_clear = CoroutineMock(return_value=True)
    client.async_send_set_effect = CoroutineMock(return_value=True)

    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: TEST_ENTITY_ID}, blocking=True
    )

    assert not client.async_send_clear.called
    assert not client.async_send_set_effect.called


async def test_light_async_turn_off(hass):
    """Test turning the light off."""
    client = create_mock_client()
    await setup_entity(hass, client=client)

    client.async_send_set_component = CoroutineMock(return_value=True)
    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: TEST_ENTITY_ID}, blocking=True
    )

    assert client.async_send_set_component.call_args == call(
        **{
            const.KEY_COMPONENTSTATE: {
                const.KEY_COMPONENT: const.KEY_COMPONENTID_LEDDEVICE,
                const.KEY_STATE: False,
            }
        }
    )

    # No calls if no state loaded.
    client.has_loaded_state = False
    client.async_send_set_component = CoroutineMock(return_value=True)
    call_registered_callback(client, "client-update", {"loaded-state": False})

    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: TEST_ENTITY_ID}, blocking=True
    )

    assert not client.async_send_set_component.called


async def test_light_async_updates_from_hyperion_client(hass):
    """Test receiving a variety of Hyperion client callbacks."""
    client = create_mock_client()
    await setup_entity(hass, client=client)

    # Bright change gets accepted.
    brightness = 10
    client.adjustment = [{const.KEY_BRIGHTNESS: brightness}]
    call_registered_callback(client, "adjustment-update")
    entity_state = hass.states.get(TEST_ENTITY_ID)
    assert entity_state.attributes["brightness"] == round(255 * (brightness / 100.0))

    # Broken brightness value is ignored.
    bad_brightness = -200
    client.adjustment = [{const.KEY_BRIGHTNESS: bad_brightness}]
    call_registered_callback(client, "adjustment-update")
    entity_state = hass.states.get(TEST_ENTITY_ID)
    assert entity_state.attributes["brightness"] == round(255 * (brightness / 100.0))

    # Update components.
    client.is_on.return_value = True
    call_registered_callback(client, "components-update")
    entity_state = hass.states.get(TEST_ENTITY_ID)
    assert entity_state.state == "on"

    client.is_on.return_value = False
    call_registered_callback(client, "components-update")
    entity_state = hass.states.get(TEST_ENTITY_ID)
    assert entity_state.state == "off"

    # Update priorities (V4L)
    client.is_on.return_value = True
    client.visible_priority = {const.KEY_COMPONENTID: const.KEY_COMPONENTID_V4L}
    call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_ENTITY_ID)
    assert entity_state.attributes["icon"] == hyperion_light.ICON_EXTERNAL_SOURCE
    assert entity_state.attributes["hs_color"] == (0.0, 0.0)
    assert entity_state.attributes["effect"] == const.KEY_COMPONENTID_V4L

    # Update priorities (Effect)
    effect = "foo"
    client.visible_priority = {
        const.KEY_COMPONENTID: const.KEY_COMPONENTID_EFFECT,
        const.KEY_OWNER: effect,
    }

    call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_ENTITY_ID)
    assert entity_state.attributes["effect"] == effect
    assert entity_state.attributes["icon"] == hyperion_light.ICON_EFFECT
    assert entity_state.attributes["hs_color"] == (0.0, 0.0)

    # Update priorities (Color)
    rgb = (0, 100, 100)
    client.visible_priority = {
        const.KEY_COMPONENTID: const.KEY_COMPONENTID_COLOR,
        const.KEY_VALUE: {const.KEY_RGB: rgb},
    }

    call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_ENTITY_ID)
    assert entity_state.attributes["effect"] == hyperion_light.KEY_EFFECT_SOLID
    assert entity_state.attributes["icon"] == hyperion_light.ICON_LIGHTBULB
    assert entity_state.attributes["hs_color"] == (180.0, 100.0)

    # Update effect list
    effects = [{const.KEY_NAME: "One"}, {const.KEY_NAME: "Two"}]
    client.effects = effects
    call_registered_callback(client, "effects-update")
    entity_state = hass.states.get(TEST_ENTITY_ID)
    assert entity_state.attributes["effect_list"] == [
        effect[const.KEY_NAME] for effect in effects
    ] + const.KEY_COMPONENTID_EXTERNAL_SOURCES + [hyperion_light.KEY_EFFECT_SOLID]

    # Update connection status (e.g. disconnection).

    # Turn on late, check state, disconnect, ensure it cannot be turned off.
    client.has_loaded_state = False
    call_registered_callback(client, "client-update", {"loaded-state": False})
    entity_state = hass.states.get(TEST_ENTITY_ID)
    assert entity_state.state == "unavailable"

    # Update connection status (e.g. re-connection)
    client.has_loaded_state = True
    call_registered_callback(client, "client-update", {"loaded-state": True})
    entity_state = hass.states.get(TEST_ENTITY_ID)
    assert entity_state.state == "on"


async def test_full_state_loaded_on_start(hass):
    """Test receiving a variety of Hyperion client callbacks."""
    client = create_mock_client()

    # Update full state (should call all update methods).
    brightness = 25
    client.adjustment = [{const.KEY_BRIGHTNESS: brightness}]
    client.visible_priority = {
        const.KEY_COMPONENTID: const.KEY_COMPONENTID_COLOR,
        const.KEY_VALUE: {const.KEY_RGB: (0, 100, 100)},
    }
    client.effects = [{const.KEY_NAME: "One"}, {const.KEY_NAME: "Two"}]

    await setup_entity(hass, client=client)

    entity_state = hass.states.get(TEST_ENTITY_ID)

    assert entity_state.attributes["brightness"] == round(255 * (brightness / 100.0))
    assert entity_state.attributes["effect"] == hyperion_light.KEY_EFFECT_SOLID
    assert entity_state.attributes["icon"] == hyperion_light.ICON_LIGHTBULB
    assert entity_state.attributes["hs_color"] == (180.0, 100.0)
