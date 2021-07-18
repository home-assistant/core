"""Test KNX expose."""
from homeassistant.components.knx import CONF_KNX_EXPOSE, KNX_ADDRESS
from homeassistant.components.knx.schema import ExposeSchema
from homeassistant.const import CONF_ATTRIBUTE, CONF_ENTITY_ID, CONF_TYPE


async def test_binary_expose(hass, knx):
    """Test a binary expose to only send telegrams on state change."""
    entity_id = "fake.entity"
    await knx.setup_integration(
        {
            CONF_KNX_EXPOSE: {
                CONF_TYPE: "binary",
                KNX_ADDRESS: "1/1/8",
                CONF_ENTITY_ID: entity_id,
            }
        },
    )
    assert not hass.states.async_all()

    # Change state to on
    hass.states.async_set(entity_id, "on", {})
    await knx.assert_write("1/1/8", True)

    # Change attribute; keep state
    hass.states.async_set(entity_id, "on", {"brightness": 180})
    await knx.assert_telegram_count(0)

    # Change attribute and state
    hass.states.async_set(entity_id, "off", {"brightness": 0})
    await knx.assert_write("1/1/8", False)


async def test_expose_attribute(hass, knx):
    """Test an expose to only send telegrams on attribute change."""
    entity_id = "fake.entity"
    attribute = "fake_attribute"
    await knx.setup_integration(
        {
            CONF_KNX_EXPOSE: {
                CONF_TYPE: "percentU8",
                KNX_ADDRESS: "1/1/8",
                CONF_ENTITY_ID: entity_id,
                CONF_ATTRIBUTE: attribute,
            }
        },
    )
    assert not hass.states.async_all()

    # Change state to "on"; no attribute
    hass.states.async_set(entity_id, "on", {})
    await knx.assert_telegram_count(0)

    # Change attribute; keep state
    hass.states.async_set(entity_id, "on", {attribute: 1})
    await knx.assert_write("1/1/8", (1,))

    # Change state keep attribute
    hass.states.async_set(entity_id, "off", {attribute: 1})
    await knx.assert_telegram_count(0)

    # Change state and attribute
    hass.states.async_set(entity_id, "on", {attribute: 0})
    await knx.assert_write("1/1/8", (0,))

    # Change state to "off"; no attribute
    hass.states.async_set(entity_id, "off", {})
    await knx.assert_telegram_count(0)


async def test_expose_attribute_with_default(hass, knx):
    """Test an expose to only send telegrams on attribute change."""
    entity_id = "fake.entity"
    attribute = "fake_attribute"
    await knx.setup_integration(
        {
            CONF_KNX_EXPOSE: {
                CONF_TYPE: "percentU8",
                KNX_ADDRESS: "1/1/8",
                CONF_ENTITY_ID: entity_id,
                CONF_ATTRIBUTE: attribute,
                ExposeSchema.CONF_KNX_EXPOSE_DEFAULT: 0,
            }
        },
    )
    assert not hass.states.async_all()

    # Change state to "on"; no attribute
    hass.states.async_set(entity_id, "on", {})
    await knx.assert_write("1/1/8", (0,))

    # Change attribute; keep state
    hass.states.async_set(entity_id, "on", {attribute: 1})
    await knx.assert_write("1/1/8", (1,))

    # Change state keep attribute
    hass.states.async_set(entity_id, "off", {attribute: 1})
    await knx.assert_no_telegram()

    # Change state and attribute
    hass.states.async_set(entity_id, "on", {attribute: 3})
    await knx.assert_write("1/1/8", (3,))

    # Change state to "off"; no attribute
    hass.states.async_set(entity_id, "off", {})
    await knx.assert_write("1/1/8", (0,))
