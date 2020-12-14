"""The tests for the Configurator component."""

import homeassistant.components.configurator as configurator
from homeassistant.const import ATTR_FRIENDLY_NAME, EVENT_TIME_CHANGED


async def test_request_least_info(hass):
    """Test request config with least amount of data."""
    request_id = configurator.async_request_config(hass, "Test Request", lambda _: None)

    assert 1 == len(
        hass.services.async_services().get(configurator.DOMAIN, [])
    ), "No new service registered"

    states = hass.states.async_all()

    assert 1 == len(states), "Expected a new state registered"

    state = states[0]

    assert configurator.STATE_CONFIGURE == state.state
    assert request_id == state.attributes.get(configurator.ATTR_CONFIGURE_ID)


async def test_request_all_info(hass):
    """Test request config with all possible info."""
    exp_attr = {
        ATTR_FRIENDLY_NAME: "Test Request",
        configurator.ATTR_DESCRIPTION: """config description

[link name](link url)

![Description image](config image url)""",
        configurator.ATTR_SUBMIT_CAPTION: "config submit caption",
        configurator.ATTR_FIELDS: [],
        configurator.ATTR_ENTITY_PICTURE: "config entity picture",
        configurator.ATTR_CONFIGURE_ID: configurator.async_request_config(
            hass,
            name="Test Request",
            callback=lambda _: None,
            description="config description",
            description_image="config image url",
            submit_caption="config submit caption",
            fields=None,
            link_name="link name",
            link_url="link url",
            entity_picture="config entity picture",
        ),
    }

    states = hass.states.async_all()
    assert 1 == len(states)
    state = states[0]

    assert configurator.STATE_CONFIGURE == state.state
    assert exp_attr == state.attributes


async def test_callback_called_on_configure(hass):
    """Test if our callback gets called when configure service called."""
    calls = []
    request_id = configurator.async_request_config(
        hass, "Test Request", lambda _: calls.append(1)
    )

    await hass.services.async_call(
        configurator.DOMAIN,
        configurator.SERVICE_CONFIGURE,
        {configurator.ATTR_CONFIGURE_ID: request_id},
    )

    await hass.async_block_till_done()
    assert 1 == len(calls), "Callback not called"


async def test_state_change_on_notify_errors(hass):
    """Test state change on notify errors."""
    request_id = configurator.async_request_config(hass, "Test Request", lambda _: None)
    error = "Oh no bad bad bad"
    configurator.async_notify_errors(hass, request_id, error)

    states = hass.states.async_all()
    assert 1 == len(states)
    state = states[0]
    assert error == state.attributes.get(configurator.ATTR_ERRORS)


async def test_notify_errors_fail_silently_on_bad_request_id(hass):
    """Test if notify errors fails silently with a bad request id."""
    configurator.async_notify_errors(hass, 2015, "Try this error")


async def test_request_done_works(hass):
    """Test if calling request done works."""
    request_id = configurator.async_request_config(hass, "Test Request", lambda _: None)
    configurator.async_request_done(hass, request_id)
    assert 1 == len(hass.states.async_all())

    hass.bus.async_fire(EVENT_TIME_CHANGED)
    await hass.async_block_till_done()
    assert 0 == len(hass.states.async_all())


async def test_request_done_fail_silently_on_bad_request_id(hass):
    """Test that request_done fails silently with a bad request id."""
    configurator.async_request_done(hass, 2016)
