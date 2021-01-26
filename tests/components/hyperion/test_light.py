"""Tests for the Hyperion integration."""
import logging
from types import MappingProxyType
from typing import Any, Optional
from unittest.mock import AsyncMock, call, patch  # type: ignore[attr-defined]

from hyperion import const

from homeassistant import setup
from homeassistant.components.hyperion import (
    get_hyperion_unique_id,
    light as hyperion_light,
)
from homeassistant.components.hyperion.const import DOMAIN, TYPE_HYPERION_LIGHT
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.config_entries import (
    ENTRY_STATE_SETUP_ERROR,
    SOURCE_REAUTH,
    ConfigEntry,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_PORT,
    CONF_SOURCE,
    CONF_TOKEN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.helpers.entity_registry import async_get_registry
from homeassistant.helpers.typing import HomeAssistantType

from . import (
    TEST_AUTH_NOT_REQUIRED_RESP,
    TEST_AUTH_REQUIRED_RESP,
    TEST_CONFIG_ENTRY_OPTIONS,
    TEST_ENTITY_ID_1,
    TEST_ENTITY_ID_2,
    TEST_ENTITY_ID_3,
    TEST_HOST,
    TEST_ID,
    TEST_INSTANCE_1,
    TEST_INSTANCE_2,
    TEST_INSTANCE_3,
    TEST_PORT,
    TEST_PRIORITY,
    TEST_SYSINFO_ID,
    TEST_YAML_ENTITY_ID,
    TEST_YAML_NAME,
    add_test_config_entry,
    create_mock_client,
    setup_test_config_entry,
)

_LOGGER = logging.getLogger(__name__)


def _call_registered_callback(
    client: AsyncMock, key: str, *args: Any, **kwargs: Any
) -> None:
    """Call a Hyperion entity callback that was registered with the client."""
    client.set_callbacks.call_args[0][0][key](*args, **kwargs)


async def _setup_entity_yaml(hass: HomeAssistantType, client: AsyncMock = None) -> None:
    """Add a test Hyperion entity to hass."""
    client = client or create_mock_client()
    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ):
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


def _get_config_entry_from_unique_id(
    hass: HomeAssistantType, unique_id: str
) -> Optional[ConfigEntry]:
    for entry in hass.config_entries.async_entries(domain=DOMAIN):
        if TEST_SYSINFO_ID == entry.unique_id:
            return entry
    return None


async def test_setup_yaml_already_converted(hass: HomeAssistantType) -> None:
    """Test an already converted YAML style config."""
    # This tests "Possibility 1" from async_setup_platform()

    # Add a pre-existing config entry.
    add_test_config_entry(hass)
    client = create_mock_client()
    await _setup_entity_yaml(hass, client=client)
    assert client.async_client_disconnect.called

    # Setup should be skipped for the YAML config as there is a pre-existing config
    # entry.
    assert hass.states.get(TEST_YAML_ENTITY_ID) is None


async def test_setup_yaml_old_style_unique_id(hass: HomeAssistantType) -> None:
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
    assert client.async_client_disconnect.called

    # The entity should have been created with the same entity_id.
    assert hass.states.get(TEST_YAML_ENTITY_ID) is not None

    # The unique_id should have been updated in the registry (rather than the one
    # specified above).
    assert registry.async_get(TEST_YAML_ENTITY_ID).unique_id == get_hyperion_unique_id(
        TEST_SYSINFO_ID, 0, TYPE_HYPERION_LIGHT
    )
    assert registry.async_get_entity_id(LIGHT_DOMAIN, DOMAIN, old_unique_id) is None

    # There should be a config entry with the correct server unique_id.
    entry = _get_config_entry_from_unique_id(hass, TEST_SYSINFO_ID)
    assert entry
    assert entry.options == MappingProxyType(TEST_CONFIG_ENTRY_OPTIONS)


async def test_setup_yaml_new_style_unique_id_wo_config(
    hass: HomeAssistantType,
) -> None:
    """Test an a new unique_id without a config entry."""
    # Note: This casde should not happen in the wild, as no released version of Home
    # Assistant should this combination, but verify correct behavior for defense in
    # depth.

    new_unique_id = get_hyperion_unique_id(TEST_SYSINFO_ID, 0, TYPE_HYPERION_LIGHT)
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
    assert client.async_client_disconnect.called

    # The entity should have been created with the same entity_id.
    assert hass.states.get(entity_id_to_preserve) is not None

    # The unique_id should have been updated in the registry (rather than the one
    # specified above).
    assert registry.async_get(entity_id_to_preserve).unique_id == new_unique_id

    # There should be a config entry with the correct server unique_id.
    entry = _get_config_entry_from_unique_id(hass, TEST_SYSINFO_ID)
    assert entry
    assert entry.options == MappingProxyType(TEST_CONFIG_ENTRY_OPTIONS)


async def test_setup_yaml_no_registry_entity(hass: HomeAssistantType) -> None:
    """Test an already converted YAML style config."""
    # This tests "Possibility 3" from async_setup_platform()

    registry = await async_get_registry(hass)

    # Add a pre-existing config entry.
    client = create_mock_client()
    await _setup_entity_yaml(hass, client=client)
    assert client.async_client_disconnect.called

    # The entity should have been created with the same entity_id.
    assert hass.states.get(TEST_YAML_ENTITY_ID) is not None

    # The unique_id should have been updated in the registry (rather than the one
    # specified above).
    assert registry.async_get(TEST_YAML_ENTITY_ID).unique_id == get_hyperion_unique_id(
        TEST_SYSINFO_ID, 0, TYPE_HYPERION_LIGHT
    )

    # There should be a config entry with the correct server unique_id.
    entry = _get_config_entry_from_unique_id(hass, TEST_SYSINFO_ID)
    assert entry
    assert entry.options == MappingProxyType(TEST_CONFIG_ENTRY_OPTIONS)


async def test_setup_yaml_not_ready(hass: HomeAssistantType) -> None:
    """Test the component not being ready."""
    client = create_mock_client()
    client.async_client_connect = AsyncMock(return_value=False)
    await _setup_entity_yaml(hass, client=client)
    assert client.async_client_disconnect.called
    assert hass.states.get(TEST_YAML_ENTITY_ID) is None


async def test_setup_config_entry(hass: HomeAssistantType) -> None:
    """Test setting up the component via config entries."""
    await setup_test_config_entry(hass, hyperion_client=create_mock_client())
    assert hass.states.get(TEST_ENTITY_ID_1) is not None


async def test_setup_config_entry_not_ready_connect_fail(
    hass: HomeAssistantType,
) -> None:
    """Test the component not being ready."""
    client = create_mock_client()
    client.async_client_connect = AsyncMock(return_value=False)
    await setup_test_config_entry(hass, hyperion_client=client)
    assert hass.states.get(TEST_ENTITY_ID_1) is None


async def test_setup_config_entry_not_ready_switch_instance_fail(
    hass: HomeAssistantType,
) -> None:
    """Test the component not being ready."""
    client = create_mock_client()
    client.async_client_switch_instance = AsyncMock(return_value=False)
    await setup_test_config_entry(hass, hyperion_client=client)
    assert client.async_client_disconnect.called
    assert hass.states.get(TEST_ENTITY_ID_1) is None


async def test_setup_config_entry_not_ready_load_state_fail(
    hass: HomeAssistantType,
) -> None:
    """Test the component not being ready."""
    client = create_mock_client()
    client.async_get_serverinfo = AsyncMock(
        return_value={
            "command": "serverinfo",
            "success": False,
        }
    )

    await setup_test_config_entry(hass, hyperion_client=client)
    assert client.async_client_disconnect.called
    assert hass.states.get(TEST_ENTITY_ID_1) is None


async def test_setup_config_entry_dynamic_instances(hass: HomeAssistantType) -> None:
    """Test dynamic changes in the omstamce configuration."""
    config_entry = add_test_config_entry(hass)

    master_client = create_mock_client()
    master_client.instances = [TEST_INSTANCE_1, TEST_INSTANCE_2]

    entity_client = create_mock_client()
    entity_client.instances = master_client.instances

    with patch(
        "homeassistant.components.hyperion.client.HyperionClient",
        side_effect=[master_client, entity_client, entity_client],
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID_1) is not None
    assert hass.states.get(TEST_ENTITY_ID_2) is not None

    # Inject a new instances update (remove instance 1, add instance 3)
    assert master_client.set_callbacks.called
    instance_callback = master_client.set_callbacks.call_args[0][0][
        f"{const.KEY_INSTANCE}-{const.KEY_UPDATE}"
    ]
    with patch(
        "homeassistant.components.hyperion.client.HyperionClient",
        return_value=entity_client,
    ):
        instance_callback(
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
    with patch(
        "homeassistant.components.hyperion.client.HyperionClient",
        return_value=entity_client,
    ):
        instance_callback(
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
    with patch(
        "homeassistant.components.hyperion.client.HyperionClient",
        return_value=entity_client,
    ):
        instance_callback(
            {
                const.KEY_SUCCESS: True,
                const.KEY_DATA: [TEST_INSTANCE_1, TEST_INSTANCE_2, TEST_INSTANCE_3],
            }
        )
        await hass.async_block_till_done()

    assert hass.states.get(TEST_ENTITY_ID_1) is not None
    assert hass.states.get(TEST_ENTITY_ID_2) is not None
    assert hass.states.get(TEST_ENTITY_ID_3) is not None


async def test_light_basic_properies(hass: HomeAssistantType) -> None:
    """Test the basic properties."""
    client = create_mock_client()
    await setup_test_config_entry(hass, hyperion_client=client)

    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
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


async def test_light_async_turn_on(hass: HomeAssistantType) -> None:
    """Test turning the light on."""
    client = create_mock_client()
    await setup_test_config_entry(hass, hyperion_client=client)

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
    client.adjustment = [{const.KEY_ID: TEST_ID}]
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID_1, ATTR_BRIGHTNESS: brightness},
        blocking=True,
    )

    assert client.async_send_set_adjustment.call_args == call(
        **{const.KEY_ADJUSTMENT: {const.KEY_BRIGHTNESS: 50, const.KEY_ID: TEST_ID}}
    )
    assert client.async_send_set_color.call_args == call(
        **{
            const.KEY_PRIORITY: TEST_PRIORITY,
            const.KEY_COLOR: [255, 255, 255],
            const.KEY_ORIGIN: hyperion_light.DEFAULT_ORIGIN,
        }
    )

    # Simulate a false return of async_send_set_adjustment
    client.async_send_set_adjustment = AsyncMock(return_value=False)
    client.adjustment = [{const.KEY_ID: TEST_ID}]
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID_1, ATTR_BRIGHTNESS: brightness},
        blocking=True,
    )

    # Simulate a state callback from Hyperion.
    client.adjustment = [{const.KEY_BRIGHTNESS: 50}]
    _call_registered_callback(client, "adjustment-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
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
    assert entity_state
    assert entity_state.attributes["hs_color"] == hs_color
    assert entity_state.attributes["icon"] == hyperion_light.ICON_LIGHTBULB

    # On (=), 100% (!), solid, [0,255,255] (=)
    brightness = 255
    client.async_send_set_color = AsyncMock(return_value=True)
    client.async_send_set_adjustment = AsyncMock(return_value=True)
    client.adjustment = [{const.KEY_ID: TEST_ID}]

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID_1, ATTR_BRIGHTNESS: brightness},
        blocking=True,
    )

    assert client.async_send_set_adjustment.call_args == call(
        **{const.KEY_ADJUSTMENT: {const.KEY_BRIGHTNESS: 100, const.KEY_ID: TEST_ID}}
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
    assert entity_state
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
    assert entity_state
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
    assert entity_state
    assert entity_state.attributes["icon"] == hyperion_light.ICON_EFFECT
    assert entity_state.attributes["effect"] == effect

    # On (=), 100% (=), [0,0,255] (!)
    # Ensure changing the color will move the effect to 'Solid' automatically.
    hs_color = (240.0, 100.0)
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
            const.KEY_COLOR: (0, 0, 255),
            const.KEY_ORIGIN: hyperion_light.DEFAULT_ORIGIN,
        }
    )
    # Simulate a state callback from Hyperion.
    client.visible_priority = {
        const.KEY_COMPONENTID: const.KEY_COMPONENTID_COLOR,
        const.KEY_VALUE: {const.KEY_RGB: (0, 0, 255)},
    }
    _call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.attributes["hs_color"] == hs_color
    assert entity_state.attributes["icon"] == hyperion_light.ICON_LIGHTBULB
    assert entity_state.attributes["effect"] == hyperion_light.KEY_EFFECT_SOLID

    # No calls if disconnected.
    client.has_loaded_state = False
    _call_registered_callback(client, "client-update", {"loaded-state": False})
    client.async_send_clear = AsyncMock(return_value=True)
    client.async_send_set_effect = AsyncMock(return_value=True)

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: TEST_ENTITY_ID_1}, blocking=True
    )

    assert not client.async_send_clear.called
    assert not client.async_send_set_effect.called


async def test_light_async_turn_off(hass: HomeAssistantType) -> None:
    """Test turning the light off."""
    client = create_mock_client()
    await setup_test_config_entry(hass, hyperion_client=client)

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

    _call_registered_callback(client, "components-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.attributes["icon"] == hyperion_light.ICON_LIGHTBULB

    # No calls if no state loaded.
    client.has_loaded_state = False
    client.async_send_set_component = AsyncMock(return_value=True)
    _call_registered_callback(client, "client-update", {"loaded-state": False})

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID_1},
        blocking=True,
    )

    assert not client.async_send_set_component.called


async def test_light_async_updates_from_hyperion_client(
    hass: HomeAssistantType,
) -> None:
    """Test receiving a variety of Hyperion client callbacks."""
    client = create_mock_client()
    await setup_test_config_entry(hass, hyperion_client=client)

    # Bright change gets accepted.
    brightness = 10
    client.adjustment = [{const.KEY_BRIGHTNESS: brightness}]
    _call_registered_callback(client, "adjustment-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.attributes["brightness"] == round(255 * (brightness / 100.0))

    # Broken brightness value is ignored.
    bad_brightness = -200
    client.adjustment = [{const.KEY_BRIGHTNESS: bad_brightness}]
    _call_registered_callback(client, "adjustment-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.attributes["brightness"] == round(255 * (brightness / 100.0))

    # Update components.
    client.is_on.return_value = True
    _call_registered_callback(client, "components-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "on"

    client.is_on.return_value = False
    _call_registered_callback(client, "components-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "off"

    # Update priorities (V4L)
    client.is_on.return_value = True
    client.visible_priority = {const.KEY_COMPONENTID: const.KEY_COMPONENTID_V4L}
    _call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
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
    assert entity_state
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
    assert entity_state
    assert entity_state.attributes["effect"] == hyperion_light.KEY_EFFECT_SOLID
    assert entity_state.attributes["icon"] == hyperion_light.ICON_LIGHTBULB
    assert entity_state.attributes["hs_color"] == (180.0, 100.0)

    # Update priorities (None)
    client.visible_priority = None

    _call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "off"

    # Update effect list
    effects = [{const.KEY_NAME: "One"}, {const.KEY_NAME: "Two"}]
    client.effects = effects
    _call_registered_callback(client, "effects-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.attributes["effect_list"] == [
        effect[const.KEY_NAME] for effect in effects
    ] + const.KEY_COMPONENTID_EXTERNAL_SOURCES + [hyperion_light.KEY_EFFECT_SOLID]

    # Update connection status (e.g. disconnection).

    # Turn on late, check state, disconnect, ensure it cannot be turned off.
    client.has_loaded_state = False
    _call_registered_callback(client, "client-update", {"loaded-state": False})
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "unavailable"

    # Update connection status (e.g. re-connection)
    client.has_loaded_state = True
    client.visible_priority = {
        const.KEY_COMPONENTID: const.KEY_COMPONENTID_COLOR,
        const.KEY_VALUE: {const.KEY_RGB: rgb},
    }
    _call_registered_callback(client, "client-update", {"loaded-state": True})
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "on"


async def test_full_state_loaded_on_start(hass: HomeAssistantType) -> None:
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

    await setup_test_config_entry(hass, hyperion_client=client)

    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.attributes["brightness"] == round(255 * (brightness / 100.0))
    assert entity_state.attributes["effect"] == hyperion_light.KEY_EFFECT_SOLID
    assert entity_state.attributes["icon"] == hyperion_light.ICON_LIGHTBULB
    assert entity_state.attributes["hs_color"] == (180.0, 100.0)


async def test_unload_entry(hass: HomeAssistantType) -> None:
    """Test unload."""
    client = create_mock_client()
    await setup_test_config_entry(hass, hyperion_client=client)
    assert hass.states.get(TEST_ENTITY_ID_1) is not None
    assert client.async_client_connect.call_count == 2
    assert not client.async_client_disconnect.called
    entry = _get_config_entry_from_unique_id(hass, TEST_SYSINFO_ID)
    assert entry

    await hass.config_entries.async_unload(entry.entry_id)
    assert client.async_client_disconnect.call_count == 2


async def test_version_log_warning(caplog, hass: HomeAssistantType) -> None:  # type: ignore[no-untyped-def]
    """Test warning on old version."""
    client = create_mock_client()
    client.async_sysinfo_version = AsyncMock(return_value="2.0.0-alpha.7")
    await setup_test_config_entry(hass, hyperion_client=client)
    assert hass.states.get(TEST_ENTITY_ID_1) is not None
    assert "Please consider upgrading" in caplog.text


async def test_version_no_log_warning(caplog, hass: HomeAssistantType) -> None:  # type: ignore[no-untyped-def]
    """Test no warning on acceptable version."""
    client = create_mock_client()
    client.async_sysinfo_version = AsyncMock(return_value="2.0.0-alpha.9")
    await setup_test_config_entry(hass, hyperion_client=client)
    assert hass.states.get(TEST_ENTITY_ID_1) is not None
    assert "Please consider upgrading" not in caplog.text


async def test_setup_entry_no_token_reauth(hass: HomeAssistantType) -> None:
    """Verify a reauth flow when auth is required but no token provided."""
    client = create_mock_client()
    config_entry = add_test_config_entry(hass)
    client.async_is_auth_required = AsyncMock(return_value=TEST_AUTH_REQUIRED_RESP)

    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ), patch.object(hass.config_entries.flow, "async_init") as mock_flow_init:
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        assert client.async_client_disconnect.called
        mock_flow_init.assert_called_once_with(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_REAUTH},
            data=config_entry.data,
        )
        assert config_entry.state == ENTRY_STATE_SETUP_ERROR


async def test_setup_entry_bad_token_reauth(hass: HomeAssistantType) -> None:
    """Verify a reauth flow when a bad token is provided."""
    client = create_mock_client()
    config_entry = add_test_config_entry(
        hass,
        data={CONF_HOST: TEST_HOST, CONF_PORT: TEST_PORT, CONF_TOKEN: "expired_token"},
    )
    client.async_is_auth_required = AsyncMock(return_value=TEST_AUTH_NOT_REQUIRED_RESP)

    # Fail to log in.
    client.async_client_login = AsyncMock(return_value=False)
    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ), patch.object(hass.config_entries.flow, "async_init") as mock_flow_init:
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        assert client.async_client_disconnect.called
        mock_flow_init.assert_called_once_with(
            DOMAIN,
            context={CONF_SOURCE: SOURCE_REAUTH},
            data=config_entry.data,
        )
        assert config_entry.state == ENTRY_STATE_SETUP_ERROR
