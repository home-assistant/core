"""Tests for the Hyperion integration."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, Mock, call, patch

from hyperion import const

from homeassistant.components.hyperion import (
    get_hyperion_device_id,
    light as hyperion_light,
)
from homeassistant.components.hyperion.const import (
    CONF_EFFECT_HIDE_LIST,
    DEFAULT_ORIGIN,
    DOMAIN,
    HYPERION_MANUFACTURER_NAME,
    HYPERION_MODEL_NAME,
    TYPE_HYPERION_PRIORITY_LIGHT,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.config_entries import (
    ENTRY_STATE_SETUP_ERROR,
    RELOAD_AFTER_UPDATE_DELAY,
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt
import homeassistant.util.color as color_util

from . import (
    TEST_AUTH_NOT_REQUIRED_RESP,
    TEST_AUTH_REQUIRED_RESP,
    TEST_CONFIG_ENTRY_ID,
    TEST_ENTITY_ID_1,
    TEST_ENTITY_ID_2,
    TEST_ENTITY_ID_3,
    TEST_HOST,
    TEST_ID,
    TEST_INSTANCE,
    TEST_INSTANCE_1,
    TEST_INSTANCE_2,
    TEST_INSTANCE_3,
    TEST_PORT,
    TEST_PRIORITY,
    TEST_PRIORITY_LIGHT_ENTITY_ID_1,
    TEST_SYSINFO_ID,
    add_test_config_entry,
    call_registered_callback,
    create_mock_client,
    register_test_entity,
    setup_test_config_entry,
)

from tests.common import async_fire_time_changed

COLOR_BLACK = color_util.COLORS["black"]


def _get_config_entry_from_unique_id(
    hass: HomeAssistant, unique_id: str
) -> ConfigEntry | None:
    for entry in hass.config_entries.async_entries(domain=DOMAIN):
        if TEST_SYSINFO_ID == entry.unique_id:
            return entry
    return None


async def test_setup_config_entry(hass: HomeAssistant) -> None:
    """Test setting up the component via config entries."""
    await setup_test_config_entry(hass, hyperion_client=create_mock_client())
    assert hass.states.get(TEST_ENTITY_ID_1) is not None


async def test_setup_config_entry_not_ready_connect_fail(
    hass: HomeAssistant,
) -> None:
    """Test the component not being ready."""
    client = create_mock_client()
    client.async_client_connect = AsyncMock(return_value=False)
    await setup_test_config_entry(hass, hyperion_client=client)
    assert hass.states.get(TEST_ENTITY_ID_1) is None


async def test_setup_config_entry_not_ready_switch_instance_fail(
    hass: HomeAssistant,
) -> None:
    """Test the component not being ready."""
    client = create_mock_client()
    client.async_client_switch_instance = AsyncMock(return_value=False)
    await setup_test_config_entry(hass, hyperion_client=client)
    assert client.async_client_disconnect.called
    assert hass.states.get(TEST_ENTITY_ID_1) is None


async def test_setup_config_entry_not_ready_load_state_fail(
    hass: HomeAssistant,
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


async def test_setup_config_entry_dynamic_instances(hass: HomeAssistant) -> None:
    """Test dynamic changes in the instance configuration."""
    registry = er.async_get(hass)

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

    assert master_client.set_callbacks.called

    # == Inject a new instances update (stop instance 1, add instance 3)
    instance_callback = master_client.set_callbacks.call_args[0][0][
        f"{const.KEY_INSTANCE}-{const.KEY_UPDATE}"
    ]

    with patch(
        "homeassistant.components.hyperion.client.HyperionClient",
        return_value=entity_client,
    ):
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

    # Instance 1 is stopped, it should still be registered.
    assert registry.async_is_registered(TEST_ENTITY_ID_1)

    # == Inject a new instances update (remove instance 1)
    assert master_client.set_callbacks.called
    instance_callback = master_client.set_callbacks.call_args[0][0][
        f"{const.KEY_INSTANCE}-{const.KEY_UPDATE}"
    ]
    with patch(
        "homeassistant.components.hyperion.client.HyperionClient",
        return_value=entity_client,
    ):
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

    # Instance 1 is removed, it should not still be registered.
    assert not registry.async_is_registered(TEST_ENTITY_ID_1)

    # == Inject a new instances update (re-add instance 1, but not running)
    with patch(
        "homeassistant.components.hyperion.client.HyperionClient",
        return_value=entity_client,
    ):
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

    # == Inject a new instances update (re-add instance 1, running)
    with patch(
        "homeassistant.components.hyperion.client.HyperionClient",
        return_value=entity_client,
    ):
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


async def test_light_basic_properies(hass: HomeAssistant) -> None:
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


async def test_light_async_turn_on(hass: HomeAssistant) -> None:
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
            const.KEY_ORIGIN: DEFAULT_ORIGIN,
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
            const.KEY_ORIGIN: DEFAULT_ORIGIN,
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
    call_registered_callback(client, "adjustment-update")
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
            const.KEY_ORIGIN: DEFAULT_ORIGIN,
        }
    )

    # Simulate a state callback from Hyperion.
    client.visible_priority = {
        const.KEY_COMPONENTID: const.KEY_COMPONENTID_COLOR,
        const.KEY_VALUE: {const.KEY_RGB: (0, 255, 255)},
    }

    call_registered_callback(client, "priorities-update")
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
            const.KEY_ORIGIN: DEFAULT_ORIGIN,
        }
    )
    client.adjustment = [{const.KEY_BRIGHTNESS: 100}]
    call_registered_callback(client, "adjustment-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.attributes["brightness"] == brightness

    # On (=), 100% (=), "USB Capture (!), [0,255,255] (=)
    component = "V4L"
    effect = const.KEY_COMPONENTID_TO_NAME[component]
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
    client.visible_priority = {const.KEY_COMPONENTID: component}
    call_registered_callback(client, "priorities-update")
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
            const.KEY_ORIGIN: DEFAULT_ORIGIN,
        }
    )
    client.visible_priority = {
        const.KEY_COMPONENTID: const.KEY_COMPONENTID_EFFECT,
        const.KEY_OWNER: effect,
    }
    call_registered_callback(client, "priorities-update")
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
            const.KEY_ORIGIN: DEFAULT_ORIGIN,
        }
    )
    # Simulate a state callback from Hyperion.
    client.visible_priority = {
        const.KEY_COMPONENTID: const.KEY_COMPONENTID_COLOR,
        const.KEY_VALUE: {const.KEY_RGB: (0, 0, 255)},
    }
    call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.attributes["hs_color"] == hs_color
    assert entity_state.attributes["icon"] == hyperion_light.ICON_LIGHTBULB
    assert entity_state.attributes["effect"] == hyperion_light.KEY_EFFECT_SOLID

    # No calls if disconnected.
    client.has_loaded_state = False
    call_registered_callback(client, "client-update", {"loaded-state": False})
    client.async_send_clear = AsyncMock(return_value=True)
    client.async_send_set_effect = AsyncMock(return_value=True)

    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: TEST_ENTITY_ID_1}, blocking=True
    )

    assert not client.async_send_clear.called
    assert not client.async_send_set_effect.called


async def test_light_async_turn_on_fail_async_send_set_component(
    hass: HomeAssistant,
) -> None:
    """Test set_component failure when turning the light on."""
    client = create_mock_client()
    client.async_send_set_component = AsyncMock(return_value=False)
    client.is_on = Mock(return_value=False)
    await setup_test_config_entry(hass, hyperion_client=client)
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: TEST_ENTITY_ID_1}, blocking=True
    )
    assert client.method_calls[-1] == call.async_send_set_component(
        componentstate={"component": "ALL", "state": True}
    )


async def test_light_async_turn_on_fail_async_send_set_component_source(
    hass: HomeAssistant,
) -> None:
    """Test async_send_set_component failure when selecting the source."""
    client = create_mock_client()
    client.async_send_clear = AsyncMock(return_value=True)
    client.async_send_set_component = AsyncMock(return_value=False)
    client.is_on = Mock(return_value=True)
    await setup_test_config_entry(hass, hyperion_client=client)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: TEST_ENTITY_ID_1,
            ATTR_EFFECT: const.KEY_COMPONENTID_TO_NAME["V4L"],
        },
        blocking=True,
    )
    assert client.method_calls[-1] == call.async_send_set_component(
        componentstate={"component": "BOBLIGHTSERVER", "state": False}
    )


async def test_light_async_turn_on_fail_async_send_clear_source(
    hass: HomeAssistant,
) -> None:
    """Test async_send_clear failure when turning the light on."""
    client = create_mock_client()
    client.is_on = Mock(return_value=True)
    client.async_send_clear = AsyncMock(return_value=False)
    await setup_test_config_entry(hass, hyperion_client=client)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: TEST_ENTITY_ID_1,
            ATTR_EFFECT: const.KEY_COMPONENTID_TO_NAME["V4L"],
        },
        blocking=True,
    )
    assert client.method_calls[-1] == call.async_send_clear(priority=180)


async def test_light_async_turn_on_fail_async_send_clear_effect(
    hass: HomeAssistant,
) -> None:
    """Test async_send_clear failure when turning on an effect."""
    client = create_mock_client()
    client.is_on = Mock(return_value=True)
    client.async_send_clear = AsyncMock(return_value=False)
    await setup_test_config_entry(hass, hyperion_client=client)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID_1, ATTR_EFFECT: "Warm Mood Blobs"},
        blocking=True,
    )
    assert client.method_calls[-1] == call.async_send_clear(priority=180)


async def test_light_async_turn_on_fail_async_send_set_effect(
    hass: HomeAssistant,
) -> None:
    """Test async_send_set_effect failure when turning on the light."""
    client = create_mock_client()
    client.is_on = Mock(return_value=True)
    client.async_send_clear = AsyncMock(return_value=True)
    client.async_send_set_effect = AsyncMock(return_value=False)
    await setup_test_config_entry(hass, hyperion_client=client)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID_1, ATTR_EFFECT: "Warm Mood Blobs"},
        blocking=True,
    )
    assert client.method_calls[-1] == call.async_send_set_effect(
        priority=180, effect={"name": "Warm Mood Blobs"}, origin="Home Assistant"
    )


async def test_light_async_turn_on_fail_async_send_set_color(
    hass: HomeAssistant,
) -> None:
    """Test async_send_set_color failure when turning on the light."""
    client = create_mock_client()
    client.is_on = Mock(return_value=True)
    client.async_send_clear = AsyncMock(return_value=True)
    client.async_send_set_color = AsyncMock(return_value=False)
    await setup_test_config_entry(hass, hyperion_client=client)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID_1, ATTR_HS_COLOR: (240.0, 100.0)},
        blocking=True,
    )
    assert client.method_calls[-1] == call.async_send_set_color(
        priority=180, color=(0, 0, 255), origin="Home Assistant"
    )


async def test_light_async_turn_off_fail_async_send_set_component(
    hass: HomeAssistant,
) -> None:
    """Test async_send_set_component failure when turning off the light."""
    client = create_mock_client()
    client.async_send_set_component = AsyncMock(return_value=False)
    await setup_test_config_entry(hass, hyperion_client=client)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID_1},
        blocking=True,
    )
    assert client.method_calls[-1] == call.async_send_set_component(
        componentstate={"component": "LEDDEVICE", "state": False}
    )


async def test_priority_light_async_turn_off_fail_async_send_clear(
    hass: HomeAssistant,
) -> None:
    """Test async_send_clear failure when turning off a priority light."""
    client = create_mock_client()
    client.async_send_clear = AsyncMock(return_value=False)
    with patch(
        "homeassistant.components.hyperion.light.HyperionPriorityLight.entity_registry_enabled_default"
    ) as enabled_by_default_mock:
        enabled_by_default_mock.return_value = True
        await setup_test_config_entry(hass, hyperion_client=client)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_PRIORITY_LIGHT_ENTITY_ID_1},
        blocking=True,
    )
    assert client.method_calls[-1] == call.async_send_clear(priority=180)


async def test_light_async_turn_off(hass: HomeAssistant) -> None:
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

    call_registered_callback(client, "components-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.attributes["icon"] == hyperion_light.ICON_LIGHTBULB

    # No calls if no state loaded.
    client.has_loaded_state = False
    client.async_send_set_component = AsyncMock(return_value=True)
    call_registered_callback(client, "client-update", {"loaded-state": False})

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID_1},
        blocking=True,
    )

    assert not client.async_send_set_component.called


async def test_light_async_updates_from_hyperion_client(
    hass: HomeAssistant,
) -> None:
    """Test receiving a variety of Hyperion client callbacks."""
    client = create_mock_client()
    await setup_test_config_entry(hass, hyperion_client=client)

    # Bright change gets accepted.
    brightness = 10
    client.adjustment = [{const.KEY_BRIGHTNESS: brightness}]
    call_registered_callback(client, "adjustment-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.attributes["brightness"] == round(255 * (brightness / 100.0))

    # Broken brightness value is ignored.
    bad_brightness = -200
    client.adjustment = [{const.KEY_BRIGHTNESS: bad_brightness}]
    call_registered_callback(client, "adjustment-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.attributes["brightness"] == round(255 * (brightness / 100.0))

    # Update components.
    client.is_on.return_value = True
    call_registered_callback(client, "components-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "on"

    client.is_on.return_value = False
    call_registered_callback(client, "components-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "off"

    # Update priorities (V4L)
    client.is_on.return_value = True
    client.visible_priority = {const.KEY_COMPONENTID: const.KEY_COMPONENTID_V4L}
    call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.attributes["icon"] == hyperion_light.ICON_EXTERNAL_SOURCE
    assert entity_state.attributes["hs_color"] == (0.0, 0.0)
    assert (
        entity_state.attributes["effect"]
        == const.KEY_COMPONENTID_TO_NAME[const.KEY_COMPONENTID_V4L]
    )

    # Update priorities (Effect)
    effect = "foo"
    client.visible_priority = {
        const.KEY_COMPONENTID: const.KEY_COMPONENTID_EFFECT,
        const.KEY_OWNER: effect,
    }

    call_registered_callback(client, "priorities-update")
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

    call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.attributes["effect"] == hyperion_light.KEY_EFFECT_SOLID
    assert entity_state.attributes["icon"] == hyperion_light.ICON_LIGHTBULB
    assert entity_state.attributes["hs_color"] == (180.0, 100.0)

    # Update priorities (None)
    client.visible_priority = None

    call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "off"

    # Update effect list
    effects = [{const.KEY_NAME: "One"}, {const.KEY_NAME: "Two"}]
    client.effects = effects
    call_registered_callback(client, "effects-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.attributes["effect_list"] == [
        hyperion_light.KEY_EFFECT_SOLID
    ] + [
        const.KEY_COMPONENTID_TO_NAME[component]
        for component in const.KEY_COMPONENTID_EXTERNAL_SOURCES
    ] + [
        effect[const.KEY_NAME] for effect in effects
    ]

    # Update connection status (e.g. disconnection).

    # Turn on late, check state, disconnect, ensure it cannot be turned off.
    client.has_loaded_state = False
    call_registered_callback(client, "client-update", {"loaded-state": False})
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "unavailable"

    # Update connection status (e.g. re-connection)
    client.has_loaded_state = True
    client.visible_priority = {
        const.KEY_COMPONENTID: const.KEY_COMPONENTID_COLOR,
        const.KEY_VALUE: {const.KEY_RGB: rgb},
    }
    call_registered_callback(client, "client-update", {"loaded-state": True})
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "on"


async def test_full_state_loaded_on_start(hass: HomeAssistant) -> None:
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


async def test_unload_entry(hass: HomeAssistant) -> None:
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


async def test_version_log_warning(caplog, hass: HomeAssistant) -> None:  # type: ignore[no-untyped-def]
    """Test warning on old version."""
    client = create_mock_client()
    client.async_sysinfo_version = AsyncMock(return_value="2.0.0-alpha.7")
    await setup_test_config_entry(hass, hyperion_client=client)
    assert hass.states.get(TEST_ENTITY_ID_1) is not None
    assert "Please consider upgrading" in caplog.text


async def test_version_no_log_warning(caplog, hass: HomeAssistant) -> None:  # type: ignore[no-untyped-def]
    """Test no warning on acceptable version."""
    client = create_mock_client()
    client.async_sysinfo_version = AsyncMock(return_value="2.0.0-alpha.9")
    await setup_test_config_entry(hass, hyperion_client=client)
    assert hass.states.get(TEST_ENTITY_ID_1) is not None
    assert "Please consider upgrading" not in caplog.text


async def test_setup_entry_no_token_reauth(hass: HomeAssistant) -> None:
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
            context={
                CONF_SOURCE: SOURCE_REAUTH,
                "entry_id": config_entry.entry_id,
                "unique_id": config_entry.unique_id,
            },
            data=config_entry.data,
        )
        assert config_entry.state == ENTRY_STATE_SETUP_ERROR


async def test_setup_entry_bad_token_reauth(hass: HomeAssistant) -> None:
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
            context={
                CONF_SOURCE: SOURCE_REAUTH,
                "entry_id": config_entry.entry_id,
                "unique_id": config_entry.unique_id,
            },
            data=config_entry.data,
        )
        assert config_entry.state == ENTRY_STATE_SETUP_ERROR


async def test_priority_light_async_updates(
    hass: HomeAssistant,
) -> None:
    """Test receiving a variety of Hyperion client callbacks to a HyperionPriorityLight."""
    priority_template = {
        const.KEY_ACTIVE: True,
        const.KEY_VISIBLE: True,
        const.KEY_PRIORITY: TEST_PRIORITY,
        const.KEY_COMPONENTID: const.KEY_COMPONENTID_COLOR,
        const.KEY_VALUE: {const.KEY_RGB: (100, 100, 100)},
    }

    client = create_mock_client()
    client.priorities = [{**priority_template}]

    register_test_entity(
        hass,
        LIGHT_DOMAIN,
        TYPE_HYPERION_PRIORITY_LIGHT,
        TEST_PRIORITY_LIGHT_ENTITY_ID_1,
    )
    await setup_test_config_entry(hass, hyperion_client=client)

    # == Scenario: Color at HA priority will show light as on.
    entity_state = hass.states.get(TEST_PRIORITY_LIGHT_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "on"
    assert entity_state.attributes["hs_color"] == (0.0, 0.0)

    # == Scenario: Color going to black shows the light as off.
    client.priorities = [
        {
            **priority_template,
            const.KEY_VALUE: {const.KEY_RGB: COLOR_BLACK},
        }
    ]
    client.visible_priority = client.priorities[0]

    call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_PRIORITY_LIGHT_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "off"

    # == Scenario: Lower priority than HA priority should have no impact on what HA
    # shows when the HA priority is present.
    client.priorities = [
        {**priority_template, const.KEY_PRIORITY: TEST_PRIORITY - 1},
        {
            **priority_template,
            const.KEY_VALUE: {const.KEY_RGB: COLOR_BLACK},
        },
    ]
    client.visible_priority = client.priorities[0]

    call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_PRIORITY_LIGHT_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "off"

    # == Scenario: Fresh color at HA priority should turn HA entity on (even though
    # there's a lower priority enabled/visible in Hyperion).
    client.priorities = [
        {**priority_template, const.KEY_PRIORITY: TEST_PRIORITY - 1},
        {
            **priority_template,
            const.KEY_PRIORITY: TEST_PRIORITY,
            const.KEY_VALUE: {const.KEY_RGB: (100, 100, 150)},
        },
    ]
    client.visible_priority = client.priorities[0]

    call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_PRIORITY_LIGHT_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "on"
    assert entity_state.attributes["hs_color"] == (240.0, 33.333)

    # == Scenario: V4L at a higher priority, with no other HA priority at all, should
    # have no effect.

    # Emulate HA turning the light off with black at the HA priority.
    client.priorities = []
    client.visible_priority = None

    call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_PRIORITY_LIGHT_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "off"

    # Emulate V4L turning on.
    client.priorities = [
        {
            **priority_template,
            const.KEY_PRIORITY: 240,
            const.KEY_COMPONENTID: const.KEY_COMPONENTID_V4L,
            const.KEY_VALUE: {const.KEY_RGB: (100, 100, 150)},
        },
    ]
    client.visible_priority = client.priorities[0]

    call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_PRIORITY_LIGHT_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "off"

    # == Scenario: A lower priority input (lower priority than HA) should have no effect.

    client.priorities = [
        {
            **priority_template,
            const.KEY_VISIBLE: True,
            const.KEY_PRIORITY: TEST_PRIORITY - 1,
            const.KEY_COMPONENTID: const.KEY_COMPONENTID_COLOR,
            const.KEY_VALUE: {const.KEY_RGB: (255, 0, 0)},
        },
        {
            **priority_template,
            const.KEY_PRIORITY: 240,
            const.KEY_COMPONENTID: const.KEY_COMPONENTID_V4L,
            const.KEY_VALUE: {const.KEY_RGB: (100, 100, 150)},
            const.KEY_VISIBLE: False,
        },
    ]

    client.visible_priority = client.priorities[0]
    call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_PRIORITY_LIGHT_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "off"

    # == Scenario: A non-active priority is ignored.
    client.priorities = [
        {
            const.KEY_ACTIVE: False,
            const.KEY_VISIBLE: False,
            const.KEY_PRIORITY: TEST_PRIORITY,
            const.KEY_COMPONENTID: const.KEY_COMPONENTID_COLOR,
            const.KEY_VALUE: {const.KEY_RGB: (100, 100, 100)},
        }
    ]
    client.visible_priority = None
    call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_PRIORITY_LIGHT_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "off"

    # == Scenario: A priority with no ... priority ... is ignored.
    client.priorities = [
        {
            const.KEY_ACTIVE: True,
            const.KEY_VISIBLE: True,
            const.KEY_COMPONENTID: const.KEY_COMPONENTID_COLOR,
            const.KEY_VALUE: {const.KEY_RGB: (100, 100, 100)},
        }
    ]
    client.visible_priority = None
    call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_PRIORITY_LIGHT_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "off"


async def test_priority_light_async_updates_off_sets_black(
    hass: HomeAssistant,
) -> None:
    """Test turning the HyperionPriorityLight off."""
    client = create_mock_client()
    client.priorities = [
        {
            const.KEY_ACTIVE: True,
            const.KEY_VISIBLE: True,
            const.KEY_PRIORITY: TEST_PRIORITY,
            const.KEY_COMPONENTID: const.KEY_COMPONENTID_COLOR,
            const.KEY_VALUE: {const.KEY_RGB: (100, 100, 100)},
        }
    ]

    register_test_entity(
        hass,
        LIGHT_DOMAIN,
        TYPE_HYPERION_PRIORITY_LIGHT,
        TEST_PRIORITY_LIGHT_ENTITY_ID_1,
    )
    await setup_test_config_entry(hass, hyperion_client=client)

    client.async_send_clear = AsyncMock(return_value=True)
    client.async_send_set_color = AsyncMock(return_value=True)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_PRIORITY_LIGHT_ENTITY_ID_1},
        blocking=True,
    )

    assert client.async_send_clear.call_args == call(
        **{
            const.KEY_PRIORITY: TEST_PRIORITY,
        }
    )

    assert client.async_send_set_color.call_args == call(
        **{
            const.KEY_PRIORITY: TEST_PRIORITY,
            const.KEY_COLOR: COLOR_BLACK,
            const.KEY_ORIGIN: DEFAULT_ORIGIN,
        }
    )


async def test_priority_light_prior_color_preserved_after_black(
    hass: HomeAssistant,
) -> None:
    """Test that color is preserved in an on->off->on cycle for a HyperionPriorityLight.

    For a HyperionPriorityLight the color black is used to indicate off. This test
    ensures that a cycle through 'off' will preserve the original color.
    """
    priority_template = {
        const.KEY_ACTIVE: True,
        const.KEY_VISIBLE: True,
        const.KEY_PRIORITY: TEST_PRIORITY,
        const.KEY_COMPONENTID: const.KEY_COMPONENTID_COLOR,
    }

    client = create_mock_client()
    client.async_send_set_color = AsyncMock(return_value=True)
    client.async_send_clear = AsyncMock(return_value=True)
    client.priorities = []
    client.visible_priority = None

    register_test_entity(
        hass,
        LIGHT_DOMAIN,
        TYPE_HYPERION_PRIORITY_LIGHT,
        TEST_PRIORITY_LIGHT_ENTITY_ID_1,
    )
    await setup_test_config_entry(hass, hyperion_client=client)

    # Turn the light on full green...
    # On (=), 100% (=), solid (=), [0,0,255] (=)
    hs_color = (240.0, 100.0)
    rgb_color = (0, 0, 255)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_PRIORITY_LIGHT_ENTITY_ID_1, ATTR_HS_COLOR: hs_color},
        blocking=True,
    )

    assert client.async_send_set_color.call_args == call(
        **{
            const.KEY_PRIORITY: TEST_PRIORITY,
            const.KEY_COLOR: rgb_color,
            const.KEY_ORIGIN: DEFAULT_ORIGIN,
        }
    )

    client.priorities = [
        {
            **priority_template,
            const.KEY_VALUE: {const.KEY_RGB: rgb_color},
        }
    ]
    client.visible_priority = client.priorities[0]
    call_registered_callback(client, "priorities-update")

    entity_state = hass.states.get(TEST_PRIORITY_LIGHT_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "on"
    assert entity_state.attributes["hs_color"] == hs_color

    # Then turn it off.
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_PRIORITY_LIGHT_ENTITY_ID_1},
        blocking=True,
    )

    assert client.async_send_set_color.call_args == call(
        **{
            const.KEY_PRIORITY: TEST_PRIORITY,
            const.KEY_COLOR: COLOR_BLACK,
            const.KEY_ORIGIN: DEFAULT_ORIGIN,
        }
    )

    client.priorities = [
        {
            **priority_template,
            const.KEY_VALUE: {const.KEY_RGB: COLOR_BLACK},
        }
    ]
    client.visible_priority = client.priorities[0]
    call_registered_callback(client, "priorities-update")

    entity_state = hass.states.get(TEST_PRIORITY_LIGHT_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "off"

    # Then turn it back on and ensure it's still green.
    # On (=), 100% (=), solid (=), [0,0,255] (=)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_PRIORITY_LIGHT_ENTITY_ID_1},
        blocking=True,
    )

    assert client.async_send_set_color.call_args == call(
        **{
            const.KEY_PRIORITY: TEST_PRIORITY,
            const.KEY_COLOR: rgb_color,
            const.KEY_ORIGIN: DEFAULT_ORIGIN,
        }
    )

    client.priorities = [
        {
            **priority_template,
            const.KEY_VALUE: {const.KEY_RGB: rgb_color},
        }
    ]
    client.visible_priority = client.priorities[0]
    call_registered_callback(client, "priorities-update")

    entity_state = hass.states.get(TEST_PRIORITY_LIGHT_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "on"
    assert entity_state.attributes["hs_color"] == hs_color


async def test_priority_light_has_no_external_sources(hass: HomeAssistant) -> None:
    """Ensure a HyperionPriorityLight does not list external sources."""
    client = create_mock_client()
    client.priorities = []

    register_test_entity(
        hass,
        LIGHT_DOMAIN,
        TYPE_HYPERION_PRIORITY_LIGHT,
        TEST_PRIORITY_LIGHT_ENTITY_ID_1,
    )
    await setup_test_config_entry(hass, hyperion_client=client)

    entity_state = hass.states.get(TEST_PRIORITY_LIGHT_ENTITY_ID_1)
    assert entity_state
    assert entity_state.attributes["effect_list"] == [hyperion_light.KEY_EFFECT_SOLID]


async def test_light_option_effect_hide_list(hass: HomeAssistant) -> None:
    """Test the effect_hide_list option."""
    client = create_mock_client()
    client.effects = [{const.KEY_NAME: "One"}, {const.KEY_NAME: "Two"}]

    await setup_test_config_entry(
        hass,
        hyperion_client=client,
        options={CONF_EFFECT_HIDE_LIST: ["Two", "USB Capture"]},
    )

    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.attributes["effect_list"] == [
        "Solid",
        "Boblight Server",
        "Platform Capture",
        "One",
    ]


async def test_device_info(hass: HomeAssistant) -> None:
    """Verify device information includes expected details."""
    client = create_mock_client()

    register_test_entity(
        hass,
        LIGHT_DOMAIN,
        TYPE_HYPERION_PRIORITY_LIGHT,
        TEST_PRIORITY_LIGHT_ENTITY_ID_1,
    )
    await setup_test_config_entry(hass, hyperion_client=client)

    device_id = get_hyperion_device_id(TEST_SYSINFO_ID, TEST_INSTANCE)
    device_registry = dr.async_get(hass)

    device = device_registry.async_get_device({(DOMAIN, device_id)})
    assert device
    assert device.config_entries == {TEST_CONFIG_ENTRY_ID}
    assert device.identifiers == {(DOMAIN, device_id)}
    assert device.manufacturer == HYPERION_MANUFACTURER_NAME
    assert device.model == HYPERION_MODEL_NAME
    assert device.name == TEST_INSTANCE_1["friendly_name"]

    entity_registry = await er.async_get_registry(hass)
    entities_from_device = [
        entry.entity_id
        for entry in er.async_entries_for_device(entity_registry, device.id)
    ]
    assert TEST_PRIORITY_LIGHT_ENTITY_ID_1 in entities_from_device
    assert TEST_ENTITY_ID_1 in entities_from_device


async def test_lights_can_be_enabled(hass: HomeAssistant) -> None:
    """Verify lights can be enabled."""
    client = create_mock_client()
    await setup_test_config_entry(hass, hyperion_client=client)

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get(TEST_PRIORITY_LIGHT_ENTITY_ID_1)
    assert entry
    assert entry.disabled
    assert entry.disabled_by == "integration"
    entity_state = hass.states.get(TEST_PRIORITY_LIGHT_ENTITY_ID_1)
    assert not entity_state

    with patch(
        "homeassistant.components.hyperion.client.HyperionClient",
        return_value=client,
    ):
        updated_entry = entity_registry.async_update_entity(
            TEST_PRIORITY_LIGHT_ENTITY_ID_1, disabled_by=None
        )
        assert not updated_entry.disabled
        await hass.async_block_till_done()

        async_fire_time_changed(  # type: ignore[no-untyped-call]
            hass,
            dt.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
        )
        await hass.async_block_till_done()

    entity_state = hass.states.get(TEST_PRIORITY_LIGHT_ENTITY_ID_1)
    assert entity_state


async def test_deprecated_effect_names(caplog, hass: HomeAssistant) -> None:  # type: ignore[no-untyped-def]
    """Test deprecated effects function and issue a warning."""
    client = create_mock_client()
    client.async_send_clear = AsyncMock(return_value=True)
    client.async_send_set_component = AsyncMock(return_value=True)

    await setup_test_config_entry(hass, hyperion_client=client)

    for component in const.KEY_COMPONENTID_EXTERNAL_SOURCES:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: TEST_ENTITY_ID_1, ATTR_EFFECT: component},
            blocking=True,
        )
        assert "Use of Hyperion effect '%s' is deprecated" % component in caplog.text

        # Simulate a state callback from Hyperion.
        client.visible_priority = {
            const.KEY_COMPONENTID: component,
        }
        call_registered_callback(client, "priorities-update")

        entity_state = hass.states.get(TEST_ENTITY_ID_1)
        assert entity_state
        assert (
            entity_state.attributes["effect"]
            == const.KEY_COMPONENTID_TO_NAME[component]
        )


async def test_deprecated_effect_names_not_in_effect_list(
    hass: HomeAssistant,
) -> None:
    """Test deprecated effects are not in shown effect list."""
    await setup_test_config_entry(hass)
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    for component in const.KEY_COMPONENTID_EXTERNAL_SOURCES:
        assert component not in entity_state.attributes["effect_list"]
