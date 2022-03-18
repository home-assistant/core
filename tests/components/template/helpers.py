"""Helper and re-usable methods for Template tests."""

from homeassistant import setup
from homeassistant.core import Context
from homeassistant.helpers.entity_platform import DATA_ENTITY_PLATFORM
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component


async def template_restore_state_test(
    hass,
    count,
    domain,
    config,
    restored_state,
    initial_state,
    initial_attributes,
    stored_attributes,
    entity_platform_name,
    entity_name,
):
    """Test restoring template entity."""

    with assert_setup_component(count, domain):
        assert await async_setup_component(
            hass,
            domain,
            config,
        )
        await hass.async_block_till_done()

        hass.states.async_set("sensor.test_state", restored_state)
        await hass.async_block_till_done()

        await hass.async_start()
        await hass.async_block_till_done()

        entity_platform = hass.data[DATA_ENTITY_PLATFORM]["template"][0]
        hass.data.pop(setup.DATA_SETUP)
        hass.config.components.remove(domain)
        await entity_platform.async_remove_entity(
            entity_platform_name + "." + entity_name
        )
        await hass.async_block_till_done()

        hass.states.async_set("sensor.test_state", "unknown")
        await hass.async_block_till_done()

        await hass.async_stop()
        await hass.async_block_till_done()

        # hass.data[DATA_ENTITY_PLATFORM]["template"] = []
        assert await async_setup_component(
            hass,
            domain,
            config,
        )
        await hass.async_block_till_done()

    entity_platform = hass.data[DATA_ENTITY_PLATFORM]["template"][-1]
    entity = entity_platform.entities[entity_platform_name + "." + entity_name]

    state = hass.states.get(entity_platform_name + "." + entity_name)
    assert state
    print(f"{state} == {initial_state}")
    assert state.state == initial_state

    state = state.as_dict()
    print(state.get("attributes"))
    for attribute, value in initial_attributes.items():
        print(
            f"{attribute}: {state.get('attributes', {}).get(attribute, None)} == {value}"
        )
        assert state.get("attributes", {}).get(attribute, None) == value

    for attribute, value in stored_attributes.items():
        print(f"{attribute}: {getattr(entity, attribute, None)} == {value}")
        assert getattr(entity, attribute, None) == value


async def trigger_restore_state_test(
    hass,
    count,
    domain,
    config,
    extra_config,
    restored_state,
    initial_state,
    initial_attributes,
    stored_attributes,
    entity_platform_name,
    entity_name,
):
    """Test restoring trigger entity."""

    config = dict(config)
    config[domain][0][entity_platform_name][0].update(**extra_config)

    with assert_setup_component(count, domain):
        assert await async_setup_component(
            hass,
            domain,
            config,
        )
        await hass.async_block_till_done()

        context = Context()
        hass.bus.async_fire("test_event", {"beer": restored_state}, context=context)
        await hass.async_block_till_done()

        await hass.async_start()
        await hass.async_block_till_done()

        entity_platform = hass.data[DATA_ENTITY_PLATFORM]["template"][0]
        print(hass.data[DATA_ENTITY_PLATFORM]["template"][0])
        hass.data.pop(setup.DATA_SETUP)
        hass.config.components.remove(domain)
        await entity_platform.async_remove_entity(
            entity_platform_name + "." + entity_name
        )
        await hass.async_block_till_done()

        await hass.async_stop()
        await hass.async_block_till_done()

        assert await async_setup_component(
            hass,
            domain,
            config,
        )
        await hass.async_block_till_done()

    entity_platform = hass.data[DATA_ENTITY_PLATFORM]["template"][-1]
    entity = entity_platform.entities[entity_platform_name + "." + entity_name]

    state = hass.states.get(entity_platform_name + "." + entity_name)
    assert state
    print(f"{state} == {initial_state}")
    assert state.state == initial_state

    state = state.as_dict()
    print(state.get("attributes"))
    for attribute, value in initial_attributes.items():
        print(
            f"{attribute}: {state.get('attributes', {}).get(attribute, None)} == {value}"
        )
        assert state.get("attributes", {}).get(attribute, None) == value

    print(entity._rendered)
    for attribute, value in stored_attributes.items():
        print(f"{attribute}: {entity._rendered.get(attribute, None)} == {value}")
        assert entity._rendered.get(attribute, None) == value
