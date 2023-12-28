"""Tests for the Hyperion integration."""
from __future__ import annotations

from unittest.mock import AsyncMock, Mock, call, patch

from hyperion import const
import pytest

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
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
    LightEntityFeature,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry, ConfigEntryState
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
    TEST_SYSINFO_ID,
    add_test_config_entry,
    call_registered_callback,
    create_mock_client,
    setup_test_config_entry,
)


def _get_config_entry_from_unique_id(
    hass: HomeAssistant, unique_id: str
) -> ConfigEntry | None:
    for entry in hass.config_entries.async_entries(domain=DOMAIN):
        if entry.unique_id == TEST_SYSINFO_ID:
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


async def test_setup_config_entry_dynamic_instances(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test dynamic changes in the instance configuration."""
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
    assert entity_registry.async_is_registered(TEST_ENTITY_ID_1)

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
    assert not entity_registry.async_is_registered(TEST_ENTITY_ID_1)

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


async def test_light_basic_properties(hass: HomeAssistant) -> None:
    """Test the basic properties."""
    client = create_mock_client()
    client.priorities = [{const.KEY_PRIORITY: TEST_PRIORITY}]
    await setup_test_config_entry(hass, hyperion_client=client)

    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "on"
    assert entity_state.attributes["brightness"] == 255
    assert entity_state.attributes["hs_color"] == (0.0, 0.0)
    assert entity_state.attributes["icon"] == hyperion_light.ICON_LIGHTBULB
    assert entity_state.attributes["effect"] == hyperion_light.KEY_EFFECT_SOLID

    # By default the effect list contains only 'Solid'.
    assert len(entity_state.attributes["effect_list"]) == 1

    assert entity_state.attributes["color_mode"] == ColorMode.HS
    assert entity_state.attributes["supported_color_modes"] == [ColorMode.HS]
    assert entity_state.attributes["supported_features"] == LightEntityFeature.EFFECT


async def test_light_async_turn_on(hass: HomeAssistant) -> None:
    """Test turning the light on."""
    client = create_mock_client()
    client.priorities = [{const.KEY_PRIORITY: TEST_PRIORITY}]
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
    client.priorities = [
        {
            const.KEY_PRIORITY: TEST_PRIORITY,
            const.KEY_COMPONENTID: const.KEY_COMPONENTID_COLOR,
            const.KEY_VALUE: {const.KEY_RGB: (0, 255, 255)},
        }
    ]

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

    assert client.async_send_set_effect.call_args == call(
        **{
            const.KEY_PRIORITY: TEST_PRIORITY,
            const.KEY_EFFECT: {const.KEY_NAME: effect},
            const.KEY_ORIGIN: DEFAULT_ORIGIN,
        }
    )
    client.priorities = [
        {
            const.KEY_PRIORITY: TEST_PRIORITY,
            const.KEY_COMPONENTID: const.KEY_COMPONENTID_EFFECT,
            const.KEY_OWNER: effect,
        }
    ]
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
    client.priorities = [
        {
            const.KEY_PRIORITY: TEST_PRIORITY,
            const.KEY_COMPONENTID: const.KEY_COMPONENTID_COLOR,
            const.KEY_VALUE: {const.KEY_RGB: (0, 0, 255)},
        }
    ]
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


async def test_light_async_turn_off_fail_async_send_send_clear(
    hass: HomeAssistant,
) -> None:
    """Test async_send_clear failure when turning off the light."""
    client = create_mock_client()
    client.async_send_clear = AsyncMock(return_value=False)
    await setup_test_config_entry(hass, hyperion_client=client)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID_1},
        blocking=True,
    )
    assert client.method_calls[-1] == call.async_send_clear(priority=TEST_PRIORITY)


async def test_light_async_turn_off(hass: HomeAssistant) -> None:
    """Test turning the light off."""
    client = create_mock_client()
    await setup_test_config_entry(hass, hyperion_client=client)

    client.async_send_clear = AsyncMock(return_value=True)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: TEST_ENTITY_ID_1},
        blocking=True,
    )

    assert client.async_send_clear.called
    assert client.async_send_clear.call_args == call(
        **{const.KEY_PRIORITY: TEST_PRIORITY}
    )


async def test_light_async_updates_from_hyperion_client(
    hass: HomeAssistant,
) -> None:
    """Test receiving a variety of Hyperion client callbacks."""
    client = create_mock_client()
    client.priorities = [{const.KEY_PRIORITY: TEST_PRIORITY}]
    await setup_test_config_entry(hass, hyperion_client=client)

    # Bright change gets accepted.
    brightness = 10
    client.adjustment = [{const.KEY_BRIGHTNESS: brightness}]
    call_registered_callback(client, "adjustment-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "on"
    assert entity_state.attributes["brightness"] == round(255 * (brightness / 100.0))

    # Broken brightness value is ignored.
    bad_brightness = -200
    client.adjustment = [{const.KEY_BRIGHTNESS: bad_brightness}]
    call_registered_callback(client, "adjustment-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "on"
    assert entity_state.attributes["brightness"] == round(255 * (brightness / 100.0))

    # Update priorities (Effect)
    effect = "foo"
    client.priorities = [
        {
            const.KEY_PRIORITY: TEST_PRIORITY,
            const.KEY_COMPONENTID: const.KEY_COMPONENTID_EFFECT,
            const.KEY_OWNER: effect,
        }
    ]

    call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.attributes["effect"] == effect
    assert entity_state.attributes["icon"] == hyperion_light.ICON_EFFECT
    assert entity_state.attributes["hs_color"] == (0.0, 0.0)

    # Update priorities (Color)
    rgb = (0, 100, 100)
    client.priorities = [
        {
            const.KEY_PRIORITY: TEST_PRIORITY,
            const.KEY_COMPONENTID: const.KEY_COMPONENTID_COLOR,
            const.KEY_VALUE: {const.KEY_RGB: rgb},
        }
    ]

    call_registered_callback(client, "priorities-update")
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.attributes["effect"] == hyperion_light.KEY_EFFECT_SOLID
    assert entity_state.attributes["icon"] == hyperion_light.ICON_LIGHTBULB
    assert entity_state.attributes["hs_color"] == (180.0, 100.0)

    # Update priorities (None)
    client.priorities = []

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
    ] + [effect[const.KEY_NAME] for effect in effects]

    # Update connection status (e.g. disconnection).

    # Turn on late, check state, disconnect, ensure it cannot be turned off.
    client.has_loaded_state = False
    call_registered_callback(client, "client-update", {"loaded-state": False})
    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.state == "unavailable"

    # Update connection status (e.g. re-connection)
    client.has_loaded_state = True
    client.priorities = [
        {
            const.KEY_PRIORITY: TEST_PRIORITY,
            const.KEY_COMPONENTID: const.KEY_COMPONENTID_COLOR,
            const.KEY_VALUE: {const.KEY_RGB: rgb},
        }
    ]
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
    client.priorities = [
        {
            const.KEY_PRIORITY: TEST_PRIORITY,
            const.KEY_COMPONENTID: const.KEY_COMPONENTID_COLOR,
            const.KEY_VALUE: {const.KEY_RGB: (0, 100, 100)},
        }
    ]
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


async def test_version_log_warning(
    caplog: pytest.LogCaptureFixture, hass: HomeAssistant
) -> None:
    """Test warning on old version."""
    client = create_mock_client()
    client.async_sysinfo_version = AsyncMock(return_value="2.0.0-alpha.7")
    await setup_test_config_entry(hass, hyperion_client=client)
    assert hass.states.get(TEST_ENTITY_ID_1) is not None
    assert "Please consider upgrading" in caplog.text


async def test_version_no_log_warning(
    caplog: pytest.LogCaptureFixture, hass: HomeAssistant
) -> None:
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
                "title_placeholders": {"name": config_entry.title},
            },
            data=config_entry.data,
        )
        assert config_entry.state is ConfigEntryState.SETUP_ERROR


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
                "title_placeholders": {"name": config_entry.title},
            },
            data=config_entry.data,
        )
        assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_light_option_effect_hide_list(hass: HomeAssistant) -> None:
    """Test the effect_hide_list option."""
    client = create_mock_client()
    client.effects = [{const.KEY_NAME: "One"}, {const.KEY_NAME: "Two"}]

    await setup_test_config_entry(
        hass,
        hyperion_client=client,
        options={CONF_EFFECT_HIDE_LIST: ["Two", "Three"]},
    )

    entity_state = hass.states.get(TEST_ENTITY_ID_1)
    assert entity_state
    assert entity_state.attributes["effect_list"] == [
        "Solid",
        "One",
    ]


async def test_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Verify device information includes expected details."""
    client = create_mock_client()

    await setup_test_config_entry(hass, hyperion_client=client)

    device_id = get_hyperion_device_id(TEST_SYSINFO_ID, TEST_INSTANCE)

    device = device_registry.async_get_device(identifiers={(DOMAIN, device_id)})
    assert device
    assert device.config_entries == {TEST_CONFIG_ENTRY_ID}
    assert device.identifiers == {(DOMAIN, device_id)}
    assert device.manufacturer == HYPERION_MANUFACTURER_NAME
    assert device.model == HYPERION_MODEL_NAME
    assert device.name == TEST_INSTANCE_1["friendly_name"]

    entities_from_device = [
        entry.entity_id
        for entry in er.async_entries_for_device(entity_registry, device.id)
    ]
    assert TEST_ENTITY_ID_1 in entities_from_device
