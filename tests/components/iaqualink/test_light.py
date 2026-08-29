"""Light platform tests for iAquaLink."""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
from iaqualink.client import AqualinkClient
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceUnauthorizedException,
)
from iaqualink.systems.iaqua.device import (
    IaquaColorLightJC,
    IaquaDimmableLight,
    IaquaLightSwitch,
)
from iaqualink.systems.iaqua.system import IaquaSystem
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
    LightEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import (
    assert_platform_setup,
    get_aqualink_device,
    get_aqualink_system,
    setup_entry,
)

from tests.common import MockConfigEntry


async def test_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all light entities are created correctly."""
    await assert_platform_setup(
        hass, config_entry, client, entity_registry, snapshot, LIGHT_DOMAIN
    )


async def _setup_light(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    cls: type,
    data: dict[str, str],
) -> tuple[IaquaSystem, object, str, object]:
    """Set up the integration with a single light entity."""
    system = get_aqualink_system(client, cls=IaquaSystem)
    system.online = True
    system.update = AsyncMock()
    light = get_aqualink_device(system, name="aux_1", cls=cls, data=data)
    system.get_devices = AsyncMock(return_value={light.name: light})
    system.set_aux = AsyncMock()
    system.set_light = AsyncMock()

    await setup_entry(hass, config_entry, system)

    entity_ids = hass.states.async_entity_ids(LIGHT_DOMAIN)
    assert len(entity_ids) == 1
    entity_id = entity_ids[0]
    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    return system, light, entity_id, entity_state


async def test_effect_light_setup_exposes_effect_features(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
) -> None:
    """Test color lights expose effect-related state through Home Assistant."""
    _, _, _, entity_state = await _setup_light(
        hass,
        config_entry,
        client,
        IaquaColorLightJC,
        {"state": "1", "aux": "1", "subtype": "1", "label": "pool light"},
    )

    assert entity_state.state == STATE_ON
    assert entity_state.attributes["color_mode"] == ColorMode.ONOFF.value
    assert entity_state.attributes["supported_features"] == LightEntityFeature.EFFECT
    assert "Alpine White" in entity_state.attributes["effect_list"]


async def test_dimmable_light_setup_exposes_brightness(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
) -> None:
    """Test dimmable lights expose brightness through Home Assistant."""
    _, _, _, entity_state = await _setup_light(
        hass,
        config_entry,
        client,
        IaquaDimmableLight,
        {"state": "1", "aux": "1", "subtype": "50", "label": "pool light"},
    )

    assert entity_state.state == STATE_ON
    assert entity_state.attributes["color_mode"] == ColorMode.BRIGHTNESS.value
    assert entity_state.attributes["brightness"] == 128


async def test_light_turn_on_with_effect_updates_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
) -> None:
    """Test turning on a color light with an effect uses the effect branch."""
    system, light, entity_id, _ = await _setup_light(
        hass,
        config_entry,
        client,
        IaquaColorLightJC,
        {"state": "0", "aux": "1", "subtype": "1", "label": "pool light"},
    )
    light_component = hass.data[LIGHT_DOMAIN]
    entity = light_component.get_entity(entity_id)
    assert entity is not None

    async def set_light(data: dict[str, str]) -> None:
        light.data["state"] = data["light"]

    system.set_light = AsyncMock(side_effect=set_light)

    await entity.async_turn_on(**{ATTR_EFFECT: "Alpine White"})

    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    assert entity_state.state == STATE_ON


async def test_light_turn_on_with_brightness_updates_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
) -> None:
    """Test turning on a dimmable light updates Home Assistant state."""
    system, light, entity_id, _ = await _setup_light(
        hass,
        config_entry,
        client,
        IaquaDimmableLight,
        {"state": "0", "aux": "1", "subtype": "0", "label": "pool light"},
    )

    async def set_light(data: dict[str, str]) -> None:
        light.data["state"] = "1" if data["light"] != "0" else "0"
        light.data["subtype"] = data["light"]

    system.set_light = AsyncMock(side_effect=set_light)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    assert entity_state.state == STATE_ON
    assert entity_state.attributes["brightness"] == 128


async def test_light_turn_on_without_attributes_updates_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
) -> None:
    """Test turning on a basic light uses the default turn_on path."""
    system, light, entity_id, _ = await _setup_light(
        hass,
        config_entry,
        client,
        IaquaLightSwitch,
        {"state": "0", "aux": "1", "label": "pool light"},
    )

    async def set_aux(_: str) -> None:
        light.data["state"] = "1"

    system.set_aux = AsyncMock(side_effect=set_aux)
    light_component = hass.data[LIGHT_DOMAIN]
    entity = light_component.get_entity(entity_id)
    assert entity is not None

    await entity.async_turn_on()

    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    assert entity_state.state == STATE_ON


@pytest.mark.parametrize(
    ("raised_exception", "expected_exception", "match"),
    [
        pytest.param(
            AqualinkServiceException,
            HomeAssistantError,
            "Aqualink error: AqualinkServiceException",
            id="service",
        ),
        pytest.param(
            TimeoutError(),
            HomeAssistantError,
            "Aqualink error: TimeoutError",
            id="timeout",
        ),
        pytest.param(
            httpx.HTTPError("boom"),
            HomeAssistantError,
            "Aqualink error: boom",
            id="http",
        ),
        pytest.param(
            AqualinkServiceUnauthorizedException,
            ConfigEntryAuthFailed,
            "Invalid credentials for iAquaLink",
            id="unauthorized",
        ),
        pytest.param(
            Exception("Test exception"),
            Exception,
            "Test exception",
            id="unexpected",
        ),
    ],
)
async def test_light_turn_off_errors_leave_state_unchanged(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: AqualinkClient,
    raised_exception: Exception | type[Exception],
    expected_exception: type[Exception],
    match: str,
) -> None:
    """Test turn-off errors are surfaced through the light service call."""
    system, _, entity_id, _ = await _setup_light(
        hass,
        config_entry,
        client,
        IaquaLightSwitch,
        {"state": "1", "aux": "1", "label": "pool light"},
    )
    system.set_aux = AsyncMock(side_effect=raised_exception)

    with pytest.raises(expected_exception, match=match):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    assert entity_state.state == STATE_ON
