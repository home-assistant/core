"""Tests for the Hyperion integration."""
import logging

from asynctest import CoroutineMock, call, patch
from hyperion import const

from homeassistant import setup
from homeassistant.components.hyperion import (
    async_unload_entry,
    get_hyperion_unique_id,
    light as hyperion_light,
)
from homeassistant.components.hyperion.const import DOMAIN
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.helpers.entity_registry import async_get_registry

from . import (
    TEST_CONFIG_ENTRY_ID,
    TEST_CONFIG_ENTRY_OPTIONS,
    TEST_ENTITY_ID_1,
    TEST_ENTITY_ID_2,
    TEST_ENTITY_ID_3,
    TEST_HOST,
    TEST_INSTANCE_1,
    TEST_INSTANCE_2,
    TEST_INSTANCE_3,
    TEST_PORT,
    TEST_PRIORITY,
    TEST_SERVER_ID,
    TEST_YAML_ENTITY_ID,
    TEST_YAML_NAME,
    add_test_config_entry,
    create_mock_client,
    setup_test_config_entry,
)

_LOGGER = logging.getLogger(__name__)


def _call_registered_callback(client, key, *args, **kwargs):
    """Call a Hyperion entity callback that was registered with the client."""
    return client.set_callbacks.call_args[0][0][key](*args, **kwargs)


async def _setup_entity_yaml(hass, client=None):
    """Add a test Hyperion entity to hass."""
    client = client or create_mock_client()
    with patch("hyperion.client.HyperionClient", return_value=client):
        assert await setup.async_setup_component(
            hass,
            LIGHT_DOMAIN,
            {
                LIGHT_DOMAIN: {
                    "platform": "hyperion",
                    "name": TEST_YAML_NAME,
                    "host": TEST_HOST,
                    "port": TEST_PORT,
                    "priority": TEST_PRIORITY,
                }
            },
        )
        await hass.async_block_till_done()


async def test_setup_yaml_already_converted(hass):
    """Test an already converted YAML style config."""
    # This tests "Possibility 1" from async_setup_platform()

    # Add a pre-existing config entry.
    add_test_config_entry(hass)
    client = create_mock_client()
    await _setup_entity_yaml(hass, client=client)

    # Setup should be skipped for the YAML config as there is a pre-existing config
    # entry.
    assert hass.states.get(TEST_YAML_ENTITY_ID) is None


async def test_setup_yaml_old_style_unique_id(hass):
    """Test an already converted YAML style config."""
    # This tests "Possibility 2" from async_setup_platform()
    old_unique_id = f"{TEST_HOST}:{TEST_PORT}-0"

    # Add a pre-existing registry entry.
    registry = await async_get_registry(hass)
    registry.async_get_or_create(
        domain=LIGHT_DOMAIN,
        platform=DOMAIN,
        unique_id=old_unique_id,
        suggested_object_id=TEST_YAML_NAME,
    )

    client = create_mock_client()
    await _setup_entity_yaml(hass, client=client)

    # The entity should have been created with the same entity_id.
    assert hass.states.get(TEST_YAML_ENTITY_ID) is not None

    # The unique_id should have been updated in the registry (rather than the one
    # specified above).
    assert registry.async_get(TEST_YAML_ENTITY_ID).unique_id == get_hyperion_unique_id(
        TEST_SERVER_ID, 0
    )
    assert registry.async_get_entity_id(LIGHT_DOMAIN, DOMAIN, old_unique_id) is None

    # There should be a config entry with the correct server unique_id.
    entry_id = next(iter(hass.data[DOMAIN]))
    assert hass.data[DOMAIN][entry_id] == client
    assert hass.config_entries.async_get_entry(entry_id).unique_id == TEST_SERVER_ID
    assert (
        hass.config_entries.async_get_entry(entry_id).options
        == TEST_CONFIG_ENTRY_OPTIONS
    )


async def test_setup_yaml_new_style_unique_id_wo_config(hass):
    """Test an a new unique_id without a config entry."""
    # Note: This casde should not happen in the wild, as no released version of Home
    # Assistant should this combination, but verify correct behavior for defense in
    # depth.

    new_unique_id = get_hyperion_unique_id(TEST_SERVER_ID, 0)
    entity_id_to_preserve = "light.magic_entity"

    # Add a pre-existing registry entry.
    registry = await async_get_registry(hass)
    registry.async_get_or_create(
        domain=LIGHT_DOMAIN,
        platform=DOMAIN,
        unique_id=new_unique_id,
        suggested_object_id=entity_id_to_preserve.split(".")[1],
    )

    client = create_mock_client()
    await _setup_entity_yaml(hass, client=client)

    # The entity should have been created with the same entity_id.
    assert hass.states.get(entity_id_to_preserve) is not None

    # The unique_id should have been updated in the registry (rather than the one
    # specified above).
    assert registry.async_get(entity_id_to_preserve).unique_id == new_unique_id

    # There should be a config entry with the correct server unique_id.
    entry_id = next(iter(hass.data[DOMAIN]))
    assert hass.data[DOMAIN][entry_id] == client
    assert hass.config_entries.async_get_entry(entry_id).unique_id == TEST_SERVER_ID
    assert (
        hass.config_entries.async_get_entry(entry_id).options
        == TEST_CONFIG_ENTRY_OPTIONS
    )


async def test_setup_yaml_no_registry_entity(hass):
    """Test an already converted YAML style config."""
    # This tests "Possibility 3" from async_setup_platform()

    registry = await async_get_registry(hass)

    # Add a pre-existing config entry.
    client = create_mock_client()
    await _setup_entity_yaml(hass, client=client)

    # The entity should have been created with the same entity_id.
    assert hass.states.get(TEST_YAML_ENTITY_ID) is not None

    # The unique_id should have been updated in the registry (rather than the one
    # specified above).
    assert registry.async_get(TEST_YAML_ENTITY_ID).unique_id == get_hyperion_unique_id(
        TEST_SERVER_ID, 0
    )

    # There should be a config entry with the correct server unique_id.
    entry_id = next(iter(hass.data[DOMAIN]))
    assert hass.data[DOMAIN][entry_id] == client
    assert hass.config_entries.async_get_entry(entry_id).unique_id == TEST_SERVER_ID
    assert (
        hass.config_entries.async_get_entry(entry_id).options
        == TEST_CONFIG_ENTRY_OPTIONS
    )


async def test_setup_yaml_not_ready(hass):
    """Test the component not being ready."""
    client = create_mock_client()
    client.async_client_connect = CoroutineMock(return_value=False)
    await _setup_entity_yaml(hass, client=client)
    assert hass.states.get(TEST_YAML_ENTITY_ID) is None


async def test_setup_config_entry(hass):
    """Test setting up the component via config entries."""
    await setup_test_config_entry(hass, client=create_mock_client())
    assert hass.states.get(TEST_ENTITY_ID_1) is not None


async def test_setup_config_entry_not_ready(hass):
    """Test the component not being ready."""
    client = create_mock_client()
    client.async_client_connect = CoroutineMock(return_value=False)
    await setup_test_config_entry(hass, client=client)
    assert hass.states.get(TEST_ENTITY_ID_1) is None


async def test_setup_config_entry_dynamic_instances(hass):
    """Test dynamic changes in the omstamce configuration."""
    config_entry = add_test_config_entry(hass)

    master_client = create_mock_client()
    master_client.instances = [TEST_INSTANCE_1, TEST_INSTANCE_2]

    entity_client = create_mock_client()
    entity_client.instances = master_client.instances

    with patch(
        "hyperion.client.HyperionClient",
        side_effect=[master_client, entity_client, entity_client],
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert master_client == hass.data[DOMAIN][TEST_CONFIG_ENTRY_ID]
    assert hass.states.get(TEST_ENTITY_ID_1) is not None
    assert hass.states.get(TEST_ENTITY_ID_2) is not None

    # Inject a new instances update (remove instance 1, add instance 3)
    assert master_client.set_callbacks.called
    instance_callback = master_client.set_callbacks.call_args[0][0][
        f"{const.KEY_INSTANCE}-{const.KEY_UPDATE}"
    ]
    with patch("hyperion.client.HyperionClient", return_value=entity_client):
        await instance_callback(
            {
                const.KEY_SUCCESS: True,
                const.KEY_DATA: [TEST_INSTANCE_2, TEST_INSTANCE_3],
            }
        )
        await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID_1) is None
    assert hass.states.get(TEST_ENTITY_ID_2) is not None
    assert hass.states.get(TEST_ENTITY_ID_3) is not None

    # Inject a new instances update (re-add instance 1, but not running)
    with patch("hyperion.client.HyperionClient", return_value=entity_client):
        await instance_callback(
            {
                const.KEY_SUCCESS: True,
                const.KEY_DATA: [
                    {**TEST_INSTANCE_1, "running": False},
                    TEST_INSTANCE_2,
                    TEST_INSTANCE_3,
                ],
            }
        )
        await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID_1) is None
    assert hass.states.get(TEST_ENTITY_ID_2) is not None
    assert hass.states.get(TEST_ENTITY_ID_3) is not None

    # Inject a new instances update (re-add instance 1, running)
    with patch("hyperion.client.HyperionClient", return_value=entity_client):
        await instance_callback(
            {
                const.KEY_SUCCESS: True,
                const.KEY_DATA: [TEST_INSTANCE_1, TEST_INSTANCE_2, TEST_INSTANCE_3],
            }
        )
        await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID_1) is not None
    assert hass.states.get(TEST_ENTITY_ID_2) is not None
    assert hass.states.get(TEST_ENTITY_ID_3) is not None


async def test_light_basic_properies(hass):
    """Test the basic properties."""
    client = create_mock_client()
    await setup_test_config_entry(hass, client=client)

    entity_state = hass.states.get(TEST_ENTITY_ID_1)
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
    await setup_test_config_entry(hass, client=client)

    # On (=), 100% (=), solid (=), [255,255,255] (=)
    client.async_send_set_color = AsyncMock(return_value=True)
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: TEST_ENTITY_ID_1}, blocking=True
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
    client.async_send_set_color = AsyncMock(return_value=True)
    client.async_send_set_adjustment = AsyncMock(return_value=True)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID_1, ATTR_BRIGHTNESS: brightness},
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
    _call_registered_callback(client, "adjustment-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state.state == "on"
    assert entity_state.attributes["brightness"] == brightness

    # On (=), 50% (=), solid (=), [0,255,255] (!)
    hs_color = (180.0, 100.0)
    client.async_send_set_color = AsyncMock(return_value=True)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID_1, ATTR_HS_COLOR: hs_color},
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

    _call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state.attributes["hs_color"] == hs_color
    assert entity_state.attributes["icon"] == hyperion_light.ICON_LIGHTBULB

    # On (=), 100% (!), solid, [0,255,255] (=)
    brightness = 255
    client.async_send_set_color = AsyncMock(return_value=True)
    client.async_send_set_adjustment = AsyncMock(return_value=True)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID_1, ATTR_BRIGHTNESS: brightness},
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
    _call_registered_callback(client, "adjustment-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state.attributes["brightness"] == brightness

    # On (=), 100% (=), V4L (!), [0,255,255] (=)
    effect = const.KEY_COMPONENTID_EXTERNAL_SOURCES[2]  # V4L
    client.async_send_clear = AsyncMock(return_value=True)
    client.async_send_set_component = AsyncMock(return_value=True)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID_1, ATTR_EFFECT: effect},
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
    _call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state.attributes["icon"] == hyperion_light.ICON_EXTERNAL_SOURCE
    assert entity_state.attributes["effect"] == effect

    # On (=), 100% (=), "Warm Blobs" (!), [0,255,255] (=)
    effect = "Warm Blobs"
    client.async_send_clear = AsyncMock(return_value=True)
    client.async_send_set_effect = AsyncMock(return_value=True)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID_1, ATTR_EFFECT: effect},
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
    _call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state.attributes["icon"] == hyperion_light.ICON_EFFECT
    assert entity_state.attributes["effect"] == effect

    # No calls if disconnected.
    client.has_loaded_state = False
    _call_registered_callback(client, "client-update", {"loaded-state": False})
    client.async_send_clear = CoroutineMock(return_value=True)
    client.async_send_set_effect = CoroutineMock(return_value=True)

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: TEST_ENTITY_ID_1}, blocking=True
    )

    assert not client.async_send_clear.called
    assert not client.async_send_set_effect.called


async def test_light_async_turn_off(hass):
    """Test turning the light off."""
    client = create_mock_client()
    await setup_test_config_entry(hass, client=client)

    client.async_send_set_component = AsyncMock(return_value=True)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID_1},
        blocking=True,
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
    _call_registered_callback(client, "client-update", {"loaded-state": False})

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID_1},
        blocking=True,
    )

    assert not client.async_send_set_component.called


async def test_light_async_updates_from_hyperion_client(hass):
    """Test receiving a variety of Hyperion client callbacks."""
    client = create_mock_client()
    await setup_test_config_entry(hass, client=client)

    # Bright change gets accepted.
    brightness = 10
    client.adjustment = [{const.KEY_BRIGHTNESS: brightness}]
    _call_registered_callback(client, "adjustment-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state.attributes["brightness"] == round(255 * (brightness / 100.0))

    # Broken brightness value is ignored.
    bad_brightness = -200
    client.adjustment = [{const.KEY_BRIGHTNESS: bad_brightness}]
    _call_registered_callback(client, "adjustment-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state.attributes["brightness"] == round(255 * (brightness / 100.0))

    # Update components.
    client.is_on.return_value = True
    _call_registered_callback(client, "components-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state.state == "on"

    client.is_on.return_value = False
    _call_registered_callback(client, "components-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state.state == "off"

    # Update priorities (V4L)
    client.is_on.return_value = True
    client.visible_priority = {const.KEY_COMPONENTID: const.KEY_COMPONENTID_V4L}
    _call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state.attributes["icon"] == hyperion_light.ICON_EXTERNAL_SOURCE
    assert entity_state.attributes["hs_color"] == (0.0, 0.0)
    assert entity_state.attributes["effect"] == const.KEY_COMPONENTID_V4L

    # Update priorities (Effect)
    effect = "foo"
    client.visible_priority = {
        const.KEY_COMPONENTID: const.KEY_COMPONENTID_EFFECT,
        const.KEY_OWNER: effect,
    }

    _call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state.attributes["effect"] == effect
    assert entity_state.attributes["icon"] == hyperion_light.ICON_EFFECT
    assert entity_state.attributes["hs_color"] == (0.0, 0.0)

    # Update priorities (Color)
    rgb = (0, 100, 100)
    client.visible_priority = {
        const.KEY_COMPONENTID: const.KEY_COMPONENTID_COLOR,
        const.KEY_VALUE: {const.KEY_RGB: rgb},
    }

    _call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state.attributes["effect"] == hyperion_light.KEY_EFFECT_SOLID
    assert entity_state.attributes["icon"] == hyperion_light.ICON_LIGHTBULB
    assert entity_state.attributes["hs_color"] == (180.0, 100.0)

    # Update effect list
    effects = [{const.KEY_NAME: "One"}, {const.KEY_NAME: "Two"}]
    client.effects = effects
    _call_registered_callback(client, "effects-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state.attributes["effect_list"] == [
        effect[const.KEY_NAME] for effect in effects
    ] + const.KEY_COMPONENTID_EXTERNAL_SOURCES + [hyperion_light.KEY_EFFECT_SOLID]

    # Update connection status (e.g. disconnection).

    # Turn on late, check state, disconnect, ensure it cannot be turned off.
    client.has_loaded_state = False
    _call_registered_callback(client, "client-update", {"loaded-state": False})
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state.state == "unavailable"

    # Update connection status (e.g. re-connection)
    client.has_loaded_state = True
    _call_registered_callback(client, "client-update", {"loaded-state": True})
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
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

    await setup_test_config_entry(hass, client=client)

    entity_state = hass.states.get(TEST_ENTITY_ID_1)

    assert entity_state.attributes["brightness"] == round(255 * (brightness / 100.0))
    assert entity_state.attributes["effect"] == hyperion_light.KEY_EFFECT_SOLID
    assert entity_state.attributes["icon"] == hyperion_light.ICON_LIGHTBULB
    assert entity_state.attributes["hs_color"] == (180.0, 100.0)


async def test_unload_entry(hass):
    """Test unload."""
    assert DOMAIN not in hass.data

    entry = await setup_test_config_entry(hass)
    assert hass.states.get(TEST_ENTITY_ID_1) is not None
    client = hass.data[DOMAIN][entry.entry_id]
    assert client.async_client_connect.called
    assert not client.async_client_disconnect.called

    assert await async_unload_entry(hass, entry)
    assert client.async_client_disconnect.called
