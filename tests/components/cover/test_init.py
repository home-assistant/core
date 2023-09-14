"""The tests for Cover."""
from unittest.mock import patch

import homeassistant.components.cover as cover
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_PLATFORM,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_TOGGLE,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er
from homeassistant.setup import async_setup_component

from tests.testing_config.custom_components.test.cover import MockCover


async def test_services(hass: HomeAssistant, enable_custom_integrations: None) -> None:
    """Test the provided services."""
    platform = getattr(hass.components, "test.cover")

    platform.init()
    assert await async_setup_component(
        hass, cover.DOMAIN, {cover.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    # ent1 = cover without tilt and position
    # ent2 = cover with position but no tilt
    # ent3 = cover with simple tilt functions and no position
    # ent4 = cover with all tilt functions but no position
    # ent5 = cover with all functions
    ent1, ent2, ent3, ent4, ent5 = platform.ENTITIES

    # Test init all covers should be open
    assert is_open(hass, ent1)
    assert is_open(hass, ent2)
    assert is_open(hass, ent3)
    assert is_open(hass, ent4)
    assert is_open(hass, ent5)

    # call basic toggle services
    await call_service(hass, SERVICE_TOGGLE, ent1)
    await call_service(hass, SERVICE_TOGGLE, ent2)
    await call_service(hass, SERVICE_TOGGLE, ent3)
    await call_service(hass, SERVICE_TOGGLE, ent4)
    await call_service(hass, SERVICE_TOGGLE, ent5)

    # entities without stop should be closed and with stop should be closing
    assert is_closed(hass, ent1)
    assert is_closing(hass, ent2)
    assert is_closed(hass, ent3)
    assert is_closed(hass, ent4)
    assert is_closing(hass, ent5)

    # call basic toggle services and set different cover position states
    await call_service(hass, SERVICE_TOGGLE, ent1)
    set_cover_position(ent2, 0)
    await call_service(hass, SERVICE_TOGGLE, ent2)
    await call_service(hass, SERVICE_TOGGLE, ent3)
    await call_service(hass, SERVICE_TOGGLE, ent4)
    set_cover_position(ent5, 15)
    await call_service(hass, SERVICE_TOGGLE, ent5)

    # entities should be in correct state depending on the SUPPORT_STOP feature and cover position
    assert is_open(hass, ent1)
    assert is_closed(hass, ent2)
    assert is_open(hass, ent3)
    assert is_open(hass, ent4)
    assert is_open(hass, ent5)

    # call basic toggle services
    await call_service(hass, SERVICE_TOGGLE, ent1)
    await call_service(hass, SERVICE_TOGGLE, ent2)
    await call_service(hass, SERVICE_TOGGLE, ent3)
    await call_service(hass, SERVICE_TOGGLE, ent4)
    await call_service(hass, SERVICE_TOGGLE, ent5)

    # entities should be in correct state depending on the SUPPORT_STOP feature and cover position
    assert is_closed(hass, ent1)
    assert is_opening(hass, ent2)
    assert is_closed(hass, ent3)
    assert is_closed(hass, ent4)
    assert is_opening(hass, ent5)


def call_service(hass, service, ent):
    """Call any service on entity."""
    return hass.services.async_call(
        cover.DOMAIN, service, {ATTR_ENTITY_ID: ent.entity_id}, blocking=True
    )


def set_cover_position(ent, position) -> None:
    """Set a position value to a cover."""
    ent._values["current_cover_position"] = position


def is_open(hass, ent):
    """Return if the cover is closed based on the statemachine."""
    return hass.states.is_state(ent.entity_id, STATE_OPEN)


def is_opening(hass, ent):
    """Return if the cover is closed based on the statemachine."""
    return hass.states.is_state(ent.entity_id, STATE_OPENING)


def is_closed(hass, ent):
    """Return if the cover is closed based on the statemachine."""
    return hass.states.is_state(ent.entity_id, STATE_CLOSED)


def is_closing(hass, ent):
    """Return if the cover is closed based on the statemachine."""
    return hass.states.is_state(ent.entity_id, STATE_CLOSING)


async def test_invert_cover_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    enable_custom_integrations: None,
) -> None:
    """Test invert cover state entity option."""
    entry = entity_registry.async_get_or_create("cover", "test", "very_unique")
    entity_id = entry.entity_id
    await hass.async_block_till_done()

    platform = getattr(hass.components, "test.cover")
    platform.init(empty=True)
    platform.ENTITIES.append(
        MockCover(
            name="test",
            is_on=True,
            unique_id="very_unique",
            current_cover_position=10,
            supported_features=cover.CoverEntityFeature.OPEN
            | cover.CoverEntityFeature.CLOSE
            | cover.CoverEntityFeature.STOP
            | cover.CoverEntityFeature.SET_POSITION,
        ),
    )

    assert await async_setup_component(hass, "cover", {"cover": {"platform": "test"}})
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OPEN
    assert state.attributes["current_position"] == 10

    entity_registry.async_update_entity_options(
        entry.entity_id, "cover", {"invert_cover_state": True}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_CLOSED
    assert state.attributes["current_position"] == 90

    entity0: MockCover = platform.ENTITIES[0]
    with patch.object(entity0, "async_close_cover") as close_cover_mock, patch.object(
        entity0, "async_open_cover"
    ) as open_cover_mock:
        await hass.services.async_call(
            cover.DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        close_cover_mock.assert_not_called()
        open_cover_mock.assert_called_once()

        close_cover_mock.reset_mock()
        open_cover_mock.reset_mock()
        await hass.services.async_call(
            cover.DOMAIN, SERVICE_OPEN_COVER, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        close_cover_mock.assert_called_once()
        open_cover_mock.assert_not_called()

    with patch.object(entity0, "async_set_cover_position") as set_cover_position_mock:
        await hass.services.async_call(
            cover.DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: entity_id, cover.ATTR_POSITION: 20},
            blocking=True,
        )
        set_cover_position_mock.assert_called_once_with(position=80)

    # TODO: Test toggle behavior


async def test_invert_cover_state_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    enable_custom_integrations: None,
) -> None:
    """Test invert cover state entity option is updated."""
    entry = entity_registry.async_get_or_create("cover", "test", "very_unique")
    entity_id = entry.entity_id
    entity_registry.async_update_entity_options(
        entity_id, "cover", {"invert_cover_state": True}
    )
    await hass.async_block_till_done()

    platform = getattr(hass.components, "test.cover")
    platform.init(empty=True)
    platform.ENTITIES.append(
        MockCover(
            name="test",
            is_on=True,
            unique_id="very_unique",
            current_cover_position=10,
            supported_features=cover.CoverEntityFeature.OPEN
            | cover.CoverEntityFeature.CLOSE
            | cover.CoverEntityFeature.STOP
            | cover.CoverEntityFeature.SET_POSITION,
        ),
    )

    assert await async_setup_component(hass, "cover", {"cover": {"platform": "test"}})
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_CLOSED
    assert state.attributes["current_position"] == 90

    entity_registry.async_update_entity_options(
        entity_id, "cover", {"invert_cover_state": False}
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OPEN
    assert state.attributes["current_position"] == 10
