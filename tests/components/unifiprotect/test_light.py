"""Test the UniFi Protect light platform."""

from typing import Any
from unittest.mock import AsyncMock

from uiprotect.data import DeviceState, Light, WSAction
from uiprotect.data.public_devices import PublicLightDeviceSettings

from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.unifiprotect.const import DEFAULT_ATTRIBUTION
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

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
    """Test light entity turn on."""

    light._api = ufp.api
    light.api.update_light_public = AsyncMock()

    setup_public_light(ufp)
    await init_entry(hass, ufp, [light, unadopted_light])
    assert_entity_counts(hass, Platform.LIGHT, 1, 1)

    entity_id = "light.test_light"
    await hass.services.async_call(
        "light", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    assert light.api.update_light_public.called
    light.api.update_light_public.assert_called_once_with(
        light.id, is_light_force_enabled=True, light_device_settings=None
    )


async def test_light_turn_on_with_brightness(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light, unadopted_light: Light
) -> None:
    """Test light entity turn on with brightness."""

    light._api = ufp.api
    light.api.update_light_public = AsyncMock()

    setup_public_light(ufp)
    await init_entry(hass, ufp, [light, unadopted_light])
    assert_entity_counts(hass, Platform.LIGHT, 1, 1)

    entity_id = "light.test_light"
    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    assert light.api.update_light_public.called
    call_kwargs = light.api.update_light_public.call_args[1]
    assert call_kwargs["is_light_force_enabled"] is True
    assert call_kwargs["light_device_settings"] is not None
    assert call_kwargs["light_device_settings"].led_level == 3  # 128/255 * 6 ≈ 3


async def test_light_turn_off(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light, unadopted_light: Light
) -> None:
    """Test light entity turn off."""

    light._api = ufp.api
    light.api.update_light_public = AsyncMock()

    setup_public_light(ufp)
    await init_entry(hass, ufp, [light, unadopted_light])
    assert_entity_counts(hass, Platform.LIGHT, 1, 1)

    entity_id = "light.test_light"
    await hass.services.async_call(
        "light", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    assert light.api.update_light_public.called
    light.api.update_light_public.assert_called_once_with(
        light.id, is_light_force_enabled=False
    )


async def test_light_setup_public_only(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    light: Light,
) -> None:
    """In public-only mode lights are enumerated from the public bootstrap."""

    public = make_public_light(light)
    ufp.api.is_public_only = True

    async def _prime_public_only() -> Any:
        pb = ufp.api.public_bootstrap
        pb.cameras = {}
        pb.lights = {light.id: public}
        return pb

    ufp.api.update_public = AsyncMock(side_effect=_prime_public_only)

    await init_entry(hass, ufp, [])
    assert_entity_counts(hass, Platform.LIGHT, 1, 1)

    entity_id = "light.test_light"
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == light.mac

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF


async def test_light_added_after_setup_public_only(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """In public-only mode a light added later is discovered from its frame.

    There is no private adopt path without a local user, so the public devices
    websocket ``add`` frame is the only discovery signal.
    """

    ufp.api.is_public_only = True

    async def _prime_public_only() -> Any:
        pb = ufp.api.public_bootstrap
        pb.cameras = {}
        pb.lights = {}
        return pb

    ufp.api.update_public = AsyncMock(side_effect=_prime_public_only)

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


async def test_light_turn_on_with_brightness_public_only(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light
) -> None:
    """Turning on with brightness sends the public settings type in public-only.

    The settings payload is copied from the device's own settings object, so in
    public-only mode it must be the public type (millisecond units), not a
    field-by-field rebuild into the private type.
    """

    public = make_public_light(light)
    public.api = ufp.api
    ufp.api.update_light_public = AsyncMock()
    ufp.api.is_public_only = True

    async def _prime_public_only() -> Any:
        pb = ufp.api.public_bootstrap
        pb.cameras = {}
        pb.lights = {light.id: public}
        return pb

    ufp.api.update_public = AsyncMock(side_effect=_prime_public_only)

    await init_entry(hass, ufp, [])
    assert_entity_counts(hass, Platform.LIGHT, 1, 1)

    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: "light.test_light", ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    call_kwargs = ufp.api.update_light_public.call_args[1]
    assert call_kwargs["is_light_force_enabled"] is True
    settings = call_kwargs["light_device_settings"]
    assert isinstance(settings, PublicLightDeviceSettings)
    assert settings.led_level == 3  # 128/255 * 6 ≈ 3
    assert settings.pir_duration == public.light_device_settings.pir_duration


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
