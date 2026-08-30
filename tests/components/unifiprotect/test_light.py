"""Test the UniFi Protect light platform."""

from collections.abc import Callable, Coroutine
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from uiprotect.data import DeviceState, Light, ModelType, Permission, WSAction
from uiprotect.websocket import WebsocketState

from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.unifiprotect.const import (
    DEFAULT_ATTRIBUTION,
    DEFAULT_BRAND,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import UNIFI_MAC
from .utils import (
    MockUFPFixture,
    adopt_devices,
    assert_entity_counts,
    init_entry,
    make_public_light,
    public_device_ws_message,
    remove_entities,
    setup_public_light,
)


def _use_public_only_bootstrap(ufp: MockUFPFixture, *publics: Mock) -> None:
    """Serve setup and resync public refreshes from a public-only bootstrap."""
    ufp.api.is_public_only = True

    async def _prime() -> Any:
        pb = ufp.api.public_bootstrap
        pb.cameras = {}
        pb.lights = {public.id: public for public in publics}
        return pb

    ufp.api.update_public = AsyncMock(side_effect=_prime)


async def test_light_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """Test removing and re-adding a light device."""

    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.LIGHT, 1, 1)
    await remove_entities(hass, ufp, [light])
    assert_entity_counts(hass, Platform.LIGHT, 0, 0)
    await adopt_devices(hass, ufp, [light])
    assert_entity_counts(hass, Platform.LIGHT, 1, 1)


async def test_light_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    light: Light,
    unadopted_light: Light,
) -> None:
    """Test light entity setup."""

    setup_public_light(ufp)
    await init_entry(hass, ufp, [light, unadopted_light])
    assert_entity_counts(hass, Platform.LIGHT, 1, 1)

    unique_id = light.mac
    entity_id = "light.test_light"

    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_light_update(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light, unadopted_light: Light
) -> None:
    """Test the light reads on/off and brightness from a public WS update."""

    setup_public_light(ufp)
    await init_entry(hass, ufp, [light, unadopted_light])
    assert_entity_counts(hass, Platform.LIGHT, 1, 1)

    # Divergent public values (on, led_level 3 -> 128) prove the read path.
    public = make_public_light(light, is_light_on=True, led_level=3)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    state = hass.states.get("light.test_light")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128


async def test_light_unavailable_without_public(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light, unadopted_light: Light
) -> None:
    """The light is unavailable without a public object."""

    await init_entry(hass, ufp, [light, unadopted_light])
    assert_entity_counts(hass, Platform.LIGHT, 1, 1)

    state = hass.states.get("light.test_light")
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_light_unavailable_on_public_disconnect(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light, unadopted_light: Light
) -> None:
    """Light availability follows the public object's connection state."""

    setup_public_light(ufp)
    await init_entry(hass, ufp, [light, unadopted_light])

    entity_id = "light.test_light"
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    public = make_public_light(light, state=DeviceState.DISCONNECTED)
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_light_brightness_none(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light, unadopted_light: Light
) -> None:
    """A light without a public LED level reports no brightness."""

    setup_public_light(ufp)
    await init_entry(hass, ufp, [light, unadopted_light])

    public = make_public_light(light, is_light_on=True)
    public.light_device_settings.led_level = None
    ufp.devices_ws_subscription(public_device_ws_message(public))
    await hass.async_block_till_done()

    state = hass.states.get("light.test_light")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] is None


async def test_light_turn_on(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light, unadopted_light: Light
) -> None:
    """Test light entity turn on (routes through the public setter)."""

    setup_public_light(ufp)
    await init_entry(hass, ufp, [light, unadopted_light])
    assert_entity_counts(hass, Platform.LIGHT, 1, 1)

    await hass.services.async_call(
        "light", "turn_on", {ATTR_ENTITY_ID: "light.test_light"}, blocking=True
    )

    ufp.api.public_bootstrap.lights[light.id].set_light.assert_awaited_once_with(
        True, None
    )


async def test_light_turn_on_with_brightness(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light, unadopted_light: Light
) -> None:
    """Test light entity turn on with brightness."""

    setup_public_light(ufp)
    await init_entry(hass, ufp, [light, unadopted_light])
    assert_entity_counts(hass, Platform.LIGHT, 1, 1)

    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: "light.test_light", ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    # 128/255 * 6 ≈ 3
    ufp.api.public_bootstrap.lights[light.id].set_light.assert_awaited_once_with(
        True, 3
    )


async def test_light_turn_off(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light, unadopted_light: Light
) -> None:
    """Test light entity turn off."""

    setup_public_light(ufp)
    await init_entry(hass, ufp, [light, unadopted_light])
    assert_entity_counts(hass, Platform.LIGHT, 1, 1)

    await hass.services.async_call(
        "light", "turn_off", {ATTR_ENTITY_ID: "light.test_light"}, blocking=True
    )

    ufp.api.public_bootstrap.lights[light.id].set_light.assert_awaited_once_with(False)


async def test_light_setup_public_only(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    light: Light,
) -> None:
    """In public-only mode lights are enumerated from the public bootstrap."""

    public = make_public_light(light)
    _use_public_only_bootstrap(ufp, public)

    await init_entry(hass, ufp, [])
    assert_entity_counts(hass, Platform.LIGHT, 1, 1)

    entity_id = "light.test_light"
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == light.mac

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF

    # Device identity comes from the public object alone.
    device = device_registry.async_get(entity.device_id)
    assert device
    assert device.model == public.type
    assert device.model_id == public.type
    assert device.manufacturer == DEFAULT_BRAND


async def test_light_added_after_setup_public_only(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    light: Light,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """In public-only mode a light added later is discovered from its frame.

    There is no private adopt path without a local user, so the public devices
    websocket ``add`` frame is the only discovery signal.
    """

    _use_public_only_bootstrap(ufp)

    await init_entry(hass, ufp, [])
    assert_entity_counts(hass, Platform.LIGHT, 0, 0)

    # A new light appears on the public devices websocket.
    public = make_public_light(light)
    ufp.api.public_bootstrap.lights = {light.id: public}
    msg = public_device_ws_message(public)
    msg.action = WSAction.ADD
    ufp.devices_ws_subscription(msg)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.LIGHT, 1, 1)
    state = hass.states.get("light.test_light")
    assert state
    assert state.state != STATE_UNAVAILABLE

    # A re-delivered add frame (e.g. the light was removed and re-added while
    # its entity is still registered) is skipped before the platform has to
    # reject the duplicate unique_id with an error.
    msg = public_device_ws_message(public)
    msg.action = WSAction.ADD
    ufp.devices_ws_subscription(msg)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.LIGHT, 1, 1)
    assert "already exists" not in caplog.text


async def test_light_added_during_gap_public_only(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    light: Light,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A light added while the websocket was down enumerates on reconnect.

    No add frame arrives for a light that appeared during the gap, so the
    reconnect resync must dispatch it for enumeration itself.
    """

    first = make_public_light(light)
    _use_public_only_bootstrap(ufp, first)

    await init_entry(hass, ufp, [])
    assert_entity_counts(hass, Platform.LIGHT, 1, 1)

    # A second light appears during the gap; the reconnect resync includes it.
    second = make_public_light(light)
    second.id = "gap-light"
    second.mac = "FFEEDDCCBB02"
    second.name = "Gap Light"
    second.display_name = "Gap Light"

    _use_public_only_bootstrap(ufp, first, second)
    ufp.devices_ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    ufp.devices_ws_state_subscription(WebsocketState.CONNECTED)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.LIGHT, 2, 2)
    assert hass.states.get("light.gap_light") is not None
    # The resync re-offers the first light too; the dedup must drop it.
    assert "already exists" not in caplog.text


@pytest.mark.parametrize(
    ("service", "service_data"),
    [
        pytest.param("turn_off", {}, id="turn_off"),
        pytest.param("turn_on", {}, id="turn_on"),
        pytest.param("turn_on", {ATTR_BRIGHTNESS: 128}, id="turn_on_with_brightness"),
    ],
)
async def test_light_command_when_public_object_vanishes(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    light: Light,
    service: str,
    service_data: dict[str, Any],
) -> None:
    """A light deleted mid-call raises a translated error, not AttributeError.

    Service calls filter unavailable entities once up front and then run the
    entity coroutines, so a delete frame landing after that check must not
    reach the command path as a missing public object.
    """

    first = make_public_light(light)
    second = make_public_light(light)
    second.id = "vanishing-light"
    second.mac = "FFEEDDCCBB03"
    second.name = "Vanishing Light"
    second.display_name = "Vanishing Light"

    _use_public_only_bootstrap(ufp, first, second)

    await init_entry(hass, ufp, [])
    assert_entity_counts(hass, Platform.LIGHT, 2, 2)

    def _delete_on_command(victim: Mock, result: Mock) -> AsyncMock:
        """Delete ``victim`` while the other light's command is running.

        Neither the deletion nor the WS dispatch below awaits, so this always
        finishes before the other entity's deferred coroutine gets a turn -
        that is what makes the outcome independent of which light HA runs
        first, not the mutual-delete shape by itself.
        """

        async def _run(*args: Any, **kwargs: Any) -> Mock:
            ufp.api.public_bootstrap.lights.pop(victim.id, None)
            msg = public_device_ws_message(victim)
            msg.new_obj = None
            msg.old_obj = victim
            ufp.devices_ws_subscription(msg)
            return result

        return AsyncMock(side_effect=_run)

    first.set_light = _delete_on_command(second, first)
    second.set_light = _delete_on_command(first, second)

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            "light",
            service,
            {
                ATTR_ENTITY_ID: ["light.test_light", "light.vanishing_light"],
                **service_data,
            },
            blocking=True,
        )

    # Which of the two runs first is HA's scheduling choice, not something
    # this test controls, so this resolves the real outcome rather than a
    # parametrized case.
    ran, missed = (first, second) if first.set_light.call_count else (second, first)
    assert ran.set_light.call_count == 1
    assert missed.set_light.call_count == 0
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "light_not_available"
    assert err.value.translation_placeholders == {"light_name": missed.display_name}


async def test_light_command_when_public_object_vanishes_hybrid(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """The hybrid guard names the light from the private object, not the public one.

    ``self.device`` is the private object in hybrid mode, whose ``display_name``
    fallback (``name or market_name or type``) differs from the public
    object's (``name or type``) - pin that the error uses it correctly here
    rather than assuming the public-only case above is equivalent.
    """

    second_light = light.model_copy()
    second_light.id = "vanishing-light"
    second_light.mac = "FFEEDDCCBB04"
    second_light.name = "Vanishing Light"

    setup_public_light(ufp)
    await init_entry(hass, ufp, [light, second_light])
    assert_entity_counts(hass, Platform.LIGHT, 2, 2)

    pb = ufp.api.public_bootstrap
    first = pb.get(ModelType.LIGHT, light.id)
    second = pb.get(ModelType.LIGHT, second_light.id)
    # setup_public_light()'s lookup re-creates a public mirror from the
    # private object whenever it's missing, which would silently heal the
    # delete below; the real bootstrap has no such fallback, so drop it here
    # to actually exercise a gone-for-good public object.
    pb.get = lambda model, obj_id: (
        pb.lights.get(obj_id) if model is ModelType.LIGHT else None
    )

    def _delete_on_command(victim: Mock, result: Mock) -> AsyncMock:
        """Delete ``victim``'s public mirror while the other light's command runs."""

        async def _run(*args: Any, **kwargs: Any) -> Mock:
            pb.lights.pop(victim.id, None)
            msg = public_device_ws_message(victim)
            msg.new_obj = None
            msg.old_obj = victim
            ufp.devices_ws_subscription(msg)
            return result

        return AsyncMock(side_effect=_run)

    first.set_light = _delete_on_command(second, first)
    second.set_light = _delete_on_command(first, second)

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            "light",
            "turn_off",
            {ATTR_ENTITY_ID: ["light.test_light", "light.vanishing_light"]},
            blocking=True,
        )

    # Same non-parametrized-order reasoning as the public-only test above.
    missed_private = second_light if first.set_light.call_count else light
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "light_not_available"
    assert err.value.translation_placeholders == {
        "light_name": missed_private.display_name
    }


async def test_light_turn_on_with_brightness_public_only(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """Turning on with brightness routes through the public setter in public-only."""

    public = make_public_light(light)
    _use_public_only_bootstrap(ufp, public)

    await init_entry(hass, ufp, [])
    assert_entity_counts(hass, Platform.LIGHT, 1, 1)

    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: "light.test_light", ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    # 128/255 * 6 ≈ 3
    public.set_light.assert_awaited_once_with(True, 3)


async def test_light_setup_no_perm(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """A light the auth user cannot write to gets no entity in hybrid mode."""

    ufp.api.bootstrap.auth_user.all_permissions = [
        Permission.unifi_dict_to_dict({"rawPermission": "light:read:*"})
    ]

    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.LIGHT, 0, 0)


async def test_light_setup_defers_to_adopt_without_private(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """Hybrid: a public light without its private object waits for the adopt.

    Creating it public-only would collide on unique_id with the entity the
    adopt dispatch creates once the private object arrives.
    """

    light._api = ufp.api
    ufp.api.public_bootstrap.lights = {light.id: make_public_light(light)}

    await init_entry(hass, ufp, [])
    assert_entity_counts(hass, Platform.LIGHT, 0, 0)

    await adopt_devices(hass, ufp, [light])
    assert_entity_counts(hass, Platform.LIGHT, 1, 1)
    state = hass.states.get("light.test_light")
    assert state
    assert state.state != STATE_UNAVAILABLE


async def test_public_only_light_end_to_end(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    light: Light,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """A public-only entry with a light in the bootstrap creates a working entity.

    Exercises the real public-only setup path (not the ``ufp`` fixture the other
    public-only tests here shim), proving lights, cameras and the alarm panel
    coexist under ``PUBLIC_ONLY_PLATFORMS``.
    """

    public = make_public_light(light, is_light_on=True, led_level=3)
    ufp_public_only.api.public_bootstrap.lights = {light.id: public}

    await setup_public_only()

    assert ufp_public_only.entry.state is ConfigEntryState.LOADED
    entity_id = "light.test_light"
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == light.mac

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128

    # The light hangs off the NVR device the public-only setup registered.
    device = device_registry.async_get(entity.device_id)
    assert device
    nvr_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, UNIFI_MAC), ufp_public_only.entry.entry_id
    )
    assert nvr_device
    assert device.via_device_id == nvr_device.id

    # Commands go to the public object; there is no private one to fall back to.
    await hass.services.async_call(
        "light",
        "turn_off",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    public.set_light.assert_awaited_once_with(False)

    assert len(hass.states.async_entity_ids(Platform.ALARM_CONTROL_PANEL.value)) == 1
