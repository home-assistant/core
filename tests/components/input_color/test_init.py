"""The tests for the input_color component."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.input_color import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HEX_COLOR,
    ATTR_KIND,
    ATTR_RGB_COLOR,
    ATTR_SOURCE_HEX,
    ATTR_XY_COLOR,
    CONF_INITIAL_COLOR,
    DOMAIN,
    SERVICE_CLEAR_BRIGHTNESS,
    SERVICE_SET_BRIGHTNESS,
    SERVICE_SET_COLOR,
)
from homeassistant.const import (
    ATTR_EDITABLE,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    SERVICE_RELOAD,
)
from homeassistant.core import Context, CoreState, HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockUser, mock_restore_cache_with_extra_data


@pytest.fixture
def storage_setup(hass: HomeAssistant, hass_storage: dict[str, Any]):
    """Storage setup."""

    async def _storage(items=None, config=None):
        if items is None:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": 1,
                "data": {
                    "items": [
                        {
                            "id": "from_storage",
                            "name": "from storage",
                            "initial_color": "#FF8000",
                        }
                    ]
                },
            }
        else:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": 1,
                "data": {"items": items},
            }
        if config is None:
            config = {DOMAIN: {}}
        return await async_setup_component(hass, DOMAIN, config)

    return _storage


async def async_set_color(
    hass: HomeAssistant, entity_id: str, data: dict[str, Any]
) -> None:
    """Set input_color color."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COLOR,
        {ATTR_ENTITY_ID: entity_id, **data},
        blocking=True,
    )


@pytest.mark.parametrize(
    "invalid_config",
    [
        None,
        {"name with space": None},
        {"test_1": {"initial_color": "#NOPE"}},
        {"test_1": {"initial_color": "#FFFFFF", "initial_kelvin": 2700}},
        {"test_1": {"initial_kelvin": 999}},
        {"test_1": {"initial_brightness": 256}},
    ],
)
async def test_config(hass: HomeAssistant, invalid_config) -> None:
    """Test config validation."""
    assert not await async_setup_component(hass, DOMAIN, {DOMAIN: invalid_config})


async def test_config_options(hass: HomeAssistant) -> None:
    """Test configuration options."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "test_1": None,
                "test_2": {
                    "name": "Evening",
                    "icon": "mdi:palette",
                    "initial_color": "#FF8000",
                    "initial_brightness": 180,
                },
                "test_3": {"initial_kelvin": 2700},
            }
        },
    )

    state_1 = hass.states.get("input_color.test_1")
    state_2 = hass.states.get("input_color.test_2")
    state_3 = hass.states.get("input_color.test_3")

    assert state_1 is not None
    assert state_1.state == "#FFFFFF"
    assert state_1.attributes[ATTR_SOURCE_HEX] == "#FFFFFF"

    assert state_2 is not None
    assert state_2.state == "#FF8000"
    assert state_2.attributes[ATTR_FRIENDLY_NAME] == "Evening"
    assert state_2.attributes[ATTR_ICON] == "mdi:palette"
    assert state_2.attributes[ATTR_BRIGHTNESS] == 180
    assert state_2.attributes[ATTR_HEX_COLOR] == "#FF8000"
    assert state_2.attributes[ATTR_RGB_COLOR] == [255, 130, 1]

    assert state_3 is not None
    assert state_3.attributes[ATTR_KIND] == "white"
    assert state_3.attributes[ATTR_COLOR_TEMP_KELVIN] == 2700
    assert state_3.attributes[ATTR_SOURCE_HEX] is None


async def test_set_color(hass: HomeAssistant) -> None:
    """Test set_color service."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"test_1": None}})
    entity_id = "input_color.test_1"

    await async_set_color(hass, entity_id, {"hex_value": "#FF8000", "brightness": 200})
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "#FF8000"
    assert state.attributes[ATTR_HEX_COLOR] == "#FF8000"
    assert state.attributes[ATTR_SOURCE_HEX] == "#FF8000"
    assert state.attributes[ATTR_BRIGHTNESS] == 200

    await async_set_color(hass, entity_id, {"rgb_color": [0, 255, 0]})
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "#00FF00"
    assert state.attributes[ATTR_SOURCE_HEX] == "#00FF00"
    assert state.attributes[ATTR_BRIGHTNESS] == 200

    await async_set_color(hass, entity_id, {"color_temp_kelvin": 2700})
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ATTR_KIND] == "white"
    assert state.attributes[ATTR_COLOR_TEMP_KELVIN] == 2700
    assert state.attributes[ATTR_SOURCE_HEX] is None


async def test_set_color_rejects_missing_or_ambiguous_input(
    hass: HomeAssistant,
) -> None:
    """Test set_color rejects invalid color shapes."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"test_1": None}})
    entity_id = "input_color.test_1"

    with pytest.raises(HomeAssistantError):
        await async_set_color(hass, entity_id, {})

    with pytest.raises(HomeAssistantError):
        await async_set_color(
            hass, entity_id, {"hex_value": "#FFFFFF", "rgb_color": [255, 255, 255]}
        )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "#FFFFFF"


async def test_brightness_services(hass: HomeAssistant) -> None:
    """Test brightness services."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"test_1": {"initial_color": "#FF8000", "initial_brightness": 100}}},
    )
    entity_id = "input_color.test_1"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_BRIGHTNESS,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 220},
        blocking=True,
    )
    assert hass.states.get(entity_id).attributes[ATTR_BRIGHTNESS] == 220

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAR_BRIGHTNESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert hass.states.get(entity_id).attributes[ATTR_BRIGHTNESS] is None


async def test_restore_state(hass: HomeAssistant) -> None:
    """Ensure states are restored on startup."""
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State("input_color.restored", "#00FF00"),
                {
                    "version": 1,
                    "xy": [0.1724, 0.7468],
                    "kind": "chromatic",
                    "kelvin": None,
                    "brightness": 123,
                    "source_hex": "#00FF00",
                },
            ),
        ),
    )

    hass.set_state(CoreState.starting)

    await async_setup_component(hass, DOMAIN, {DOMAIN: {"restored": None}})

    state = hass.states.get("input_color.restored")
    assert state is not None
    assert state.state == "#00FF00"
    assert state.attributes[ATTR_BRIGHTNESS] == 123
    assert state.attributes[ATTR_SOURCE_HEX] == "#00FF00"


async def test_initial_state_overrules_restore_state(hass: HomeAssistant) -> None:
    """Ensure initial config overrules restored state."""
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State("input_color.restored", "#00FF00"),
                {
                    "version": 1,
                    "xy": [0.1724, 0.7468],
                    "kind": "chromatic",
                    "kelvin": None,
                    "brightness": 123,
                    "source_hex": "#00FF00",
                },
            ),
        ),
    )

    hass.set_state(CoreState.starting)

    await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"restored": {CONF_INITIAL_COLOR: "#FF0000"}}}
    )

    state = hass.states.get("input_color.restored")
    assert state is not None
    assert state.state == "#FF0000"
    assert state.attributes[ATTR_SOURCE_HEX] == "#FF0000"


async def test_input_color_context(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test that input_color context works."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"test_1": None}})
    entity_id = "input_color.test_1"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COLOR,
        {ATTR_ENTITY_ID: entity_id, "hex_value": "#00FF00"},
        True,
        Context(user_id=hass_admin_user.id),
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.context.user_id == hass_admin_user.id


async def test_reload(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, hass_admin_user: MockUser
) -> None:
    """Test reload service."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "test_1": None,
                "test_2": {"name": "Evening", "initial_color": "#FF8000"},
            }
        },
    )

    assert hass.states.get("input_color.test_1") is not None
    assert hass.states.get("input_color.test_2").state == "#FF8000"
    assert hass.states.get("input_color.test_3") is None
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, "test_1") is not None

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={
            DOMAIN: {
                "test_2": {"name": "Evening reloaded", "initial_color": "#0000FF"},
                "test_3": None,
            }
        },
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )

    assert hass.states.get("input_color.test_1") is None
    assert hass.states.get("input_color.test_2").state == "#FF8000"
    assert (
        hass.states.get("input_color.test_2").attributes[ATTR_FRIENDLY_NAME]
        == "Evening reloaded"
    )
    assert hass.states.get("input_color.test_3") is not None


async def test_storage_load(storage_setup) -> None:
    """Test loading input_color from storage."""
    assert await storage_setup()


async def test_editable_attribute(hass: HomeAssistant, storage_setup) -> None:
    """Test editable attribute for storage and yaml helpers."""
    assert await storage_setup(
        config={DOMAIN: {"from_yaml": {"name": "from yaml"}}},
    )

    yaml_state = hass.states.get("input_color.from_yaml")
    storage_state = hass.states.get("input_color.from_storage")
    assert yaml_state is not None
    assert storage_state is not None
    assert yaml_state.attributes[ATTR_EDITABLE] is False
    assert storage_state.attributes[ATTR_EDITABLE] is True
    assert storage_state.attributes[ATTR_FRIENDLY_NAME] == "from storage"


async def test_xy_attrs_are_rounded(hass: HomeAssistant) -> None:
    """Test xy attributes are rounded for state output."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {"test_1": None}})
    entity_id = "input_color.test_1"

    await async_set_color(hass, entity_id, {"xy_color": [0.123456, 0.654321]})

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ATTR_XY_COLOR] == [0.1235, 0.6543]
