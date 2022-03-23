"""Helper and re-usable methods for Template tests."""

from homeassistant.core import Context, CoreState, State
from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, mock_restore_cache_with_extra_data


async def template_save_state(
    hass,
    count,
    domain,
    platform,
    config,
    save_data,
):
    """Test for saving data for a template."""
    entity_name = "restore"
    with assert_setup_component(count, domain):
        assert await async_setup_component(
            hass,
            domain,
            config,
        )
        await hass.async_block_till_done()

        # hass.states.async_set("sensor.test_state", set_state)
        # await hass.async_block_till_done()

    entity_comp = hass.data.get(DATA_INSTANCES, {}).get(platform)
    entity = entity_comp.get_entity(platform + "." + entity_name)

    restored_extra_data = entity.extra_restore_state_data.as_dict()

    for attribute, value in save_data.items():
        print(f"{attribute}: {restored_extra_data.get(attribute, None)} == {value}")
        assert restored_extra_data.get(attribute, None) == value


async def template_restore_state(
    hass,
    count,
    domain,
    platform,
    config,
    restored_state,
    state_attributes,
    additional_attributes,
    save_data,
):
    """Test for restoring data for a template."""
    entity_name = "restore"

    fake_state = State(platform + "." + entity_name, restored_state, state_attributes)

    mock_restore_cache_with_extra_data(hass, ((fake_state, save_data),))

    hass.state = CoreState.not_running
    with assert_setup_component(count, domain):
        assert await async_setup_component(
            hass,
            domain,
            config,
        )
        await hass.async_block_till_done()

    state = hass.states.get(platform + "." + entity_name)
    assert state
    print(f"{state} == {restored_state}")
    assert state.state == restored_state

    state = state.as_dict()

    for attribute, value in state_attributes.items():
        print(
            f"{attribute}: {state.get('attributes', {}).get(attribute, None)} == {value}"
        )
        assert state.get("attributes", {}).get(attribute, None) == value

    entity_comp = hass.data.get(DATA_INSTANCES, {}).get(platform)
    entity = entity_comp.get_entity(platform + "." + entity_name)
    for attribute, value in additional_attributes.items():
        print(f"{attribute}: {getattr(entity, attribute, None)} == {value}")
        assert getattr(entity, attribute, None) == value


async def trigger_save_state(
    hass,
    count,
    domain,
    platform,
    config,
    save_data,
):
    """Test for saving data for a trigger."""
    entity_name = "template_restore"
    with assert_setup_component(count, domain):
        assert await async_setup_component(
            hass,
            domain,
            config,
        )
        await hass.async_block_till_done()

        context = Context()
        hass.bus.async_fire("test_event", {"beer": 1}, context=context)
        await hass.async_block_till_done()

    entity_comp = hass.data.get(DATA_INSTANCES, {}).get(platform)
    entity = entity_comp.get_entity(platform + "." + entity_name)

    restored_extra_data = entity.extra_restore_state_data.as_dict()

    for attribute, value in save_data.items():
        print(f"{attribute}: {restored_extra_data.get(attribute, None)} == {value}")
        assert restored_extra_data.get(attribute, None) == value


async def trigger_restore_state(
    hass,
    count,
    domain,
    platform,
    config,
    restored_state,
    state_attributes,
    additional_attributes,
    save_data,
):
    """Test for restoring data for a trigger."""
    entity_name = "template_restore"

    fake_state = State(platform + "." + entity_name, restored_state, state_attributes)

    mock_restore_cache_with_extra_data(hass, ((fake_state, save_data),))

    hass.state = CoreState.not_running
    with assert_setup_component(count, domain):
        assert await async_setup_component(
            hass,
            domain,
            config,
        )
        await hass.async_block_till_done()

    state = hass.states.get(platform + "." + entity_name)
    assert state
    print(f"{state} == {restored_state}")
    assert state.state == restored_state

    state = state.as_dict()
    for attribute, value in state_attributes.items():
        print(
            f"{attribute}: {state.get('attributes', {}).get(attribute, None)} == {value}"
        )
        assert state.get("attributes", {}).get(attribute, None) == value

    entity_comp = hass.data.get(DATA_INSTANCES, {}).get(platform)
    entity = entity_comp.get_entity(platform + "." + entity_name)

    for attribute, value in additional_attributes.items():
        print(f"{attribute}: {entity._rendered.get(attribute, None)} == {value}")
        assert entity._rendered.get(attribute, None) == value
