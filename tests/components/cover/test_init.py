"""The tests for Cover."""
import homeassistant.components.cover as cover
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_PLATFORM,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_TOGGLE,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.setup import async_setup_component


async def test_services(hass, enable_custom_integrations):
    """Test the provided services."""
    platform = getattr(hass.components, "test.cover")

    platform.init()
    assert await async_setup_component(
        hass, cover.DOMAIN, {cover.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await hass.async_block_till_done()

    ent1, ent2, ent3, ent4 = platform.ENTITIES

    # Test init
    assert is_open(hass, ent1.entity_id)
    assert is_open(hass, ent2.entity_id)
    assert is_open(hass, ent3.entity_id)
    assert is_open(hass, ent4.entity_id)

    # Test basic turn_on, turn_off, toggle services
    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ent1.entity_id},
        blocking=True,
    )
    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: ent2.entity_id},
        blocking=True,
    )
    await hass.services.async_call(
        cover.DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: ent3.entity_id}, blocking=True
    )
    await hass.services.async_call(
        cover.DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: ent4.entity_id}, blocking=True
    )

    assert is_opening(hass, ent1.entity_id)
    assert is_closing(hass, ent2.entity_id)
    assert is_closing(hass, ent3.entity_id)
    assert is_closing(hass, ent4.entity_id)

    await hass.services.async_call(
        cover.DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: ent1.entity_id}, blocking=True
    )
    await hass.services.async_call(
        cover.DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: ent2.entity_id}, blocking=True
    )
    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ent3.entity_id},
        blocking=True,
    )
    await hass.services.async_call(
        cover.DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: ent4.entity_id},
        blocking=True,
    )

    assert is_open(hass, ent1.entity_id)
    assert cover.is_closed(hass, ent2.entity_id)
    assert is_opening(hass, ent3.entity_id)
    assert is_opening(hass, ent4.entity_id)

    await hass.services.async_call(
        cover.DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: ent1.entity_id}, blocking=True
    )
    await hass.services.async_call(
        cover.DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: ent2.entity_id}, blocking=True
    )
    await hass.services.async_call(
        cover.DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: ent3.entity_id}, blocking=True
    )
    await hass.services.async_call(
        cover.DOMAIN, SERVICE_TOGGLE, {ATTR_ENTITY_ID: ent4.entity_id}, blocking=True
    )

    assert is_closing(hass, ent1.entity_id)
    assert is_opening(hass, ent2.entity_id)
    assert is_open(hass, ent3.entity_id)
    assert is_open(hass, ent4.entity_id)


def is_open(hass, entity_id):
    """Return if the cover is closed based on the statemachine."""
    return hass.states.is_state(entity_id, STATE_OPEN)


def is_opening(hass, entity_id):
    """Return if the cover is closed based on the statemachine."""
    return hass.states.is_state(entity_id, STATE_OPENING)


def is_closed(hass, entity_id):
    """Return if the cover is closed based on the statemachine."""
    return hass.states.is_state(entity_id, STATE_CLOSED)


def is_closing(hass, entity_id):
    """Return if the cover is closed based on the statemachine."""
    return hass.states.is_state(entity_id, STATE_CLOSING)


def test_deprecated_base_class(caplog):
    """Test deprecated base class."""

    class CustomCover(cover.CoverDevice):
        pass

    CustomCover()
    assert "CoverDevice is deprecated, modify CustomCover" in caplog.text
