"""Test the Quotable integration."""
from ast import literal_eval

from homeassistant.components.quotable.const import (
    ATTR_AUTHOR,
    ATTR_BG_COLOR,
    ATTR_CONTENT,
    ATTR_QUOTES,
    ATTR_SELECTED_AUTHORS,
    ATTR_SELECTED_TAGS,
    ATTR_STYLES,
    ATTR_TEXT_COLOR,
    ATTR_UPDATE_FREQUENCY,
    DOMAIN,
    ENTITY_ID,
    EVENT_NEW_QUOTE_FETCHED,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_async_setup(hass: HomeAssistant) -> None:
    """Test that the integration is correctly set up."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})


async def test_default_config(hass: HomeAssistant) -> None:
    """Test that default config values are used when config is empty in configuration.yaml."""

    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    config = hass.data.get(DOMAIN).config

    assert config[ATTR_UPDATE_FREQUENCY] == 1800
    assert config[ATTR_STYLES][ATTR_BG_COLOR] == "#038fc7"
    assert config[ATTR_STYLES][ATTR_TEXT_COLOR] == "#212121"


async def test_update_configuration(hass: HomeAssistant) -> None:
    """Test that config values are correctly updated."""

    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    quotable = hass.data.get(DOMAIN)

    assert not quotable.config[ATTR_SELECTED_TAGS]
    assert not quotable.config[ATTR_SELECTED_AUTHORS]

    selected_tags = ["science", "love"]
    selected_authors = ["albert-einstien", "rumi"]
    update_frequency = 30
    styles = {ATTR_BG_COLOR: "#000", ATTR_TEXT_COLOR: "#fff"}

    quotable.update_configuration(
        selected_tags, selected_authors, update_frequency, styles
    )

    assert quotable.config[ATTR_SELECTED_TAGS] == selected_tags
    assert quotable.config[ATTR_SELECTED_AUTHORS] == selected_authors
    assert quotable.config[ATTR_UPDATE_FREQUENCY] == update_frequency
    assert quotable.config[ATTR_STYLES] == styles

    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_SELECTED_TAGS] == selected_tags
    assert state.attributes[ATTR_SELECTED_AUTHORS] == selected_authors
    assert state.attributes[ATTR_UPDATE_FREQUENCY] == update_frequency
    assert state.attributes[ATTR_STYLES] == styles


async def test_new_quote_fetched_event(hass: HomeAssistant) -> None:
    """Test that new_quote_fetched event is handled correctly."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert not literal_eval(state.attributes[ATTR_QUOTES])

    quote_1 = {
        ATTR_AUTHOR: "Albert Einstein",
        ATTR_CONTENT: "You can't blame gravity for falling in love.",
    }
    hass.bus.async_fire(EVENT_NEW_QUOTE_FETCHED, quote_1)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    quotes = literal_eval(state.attributes[ATTR_QUOTES])
    assert len(quotes) == 1
    assert quotes[0] == quote_1

    """Test that newly fetched quotes are added to the beginning of the list."""
    quote_2 = {
        ATTR_AUTHOR: "Rumi",
        ATTR_CONTENT: "Patience is the key to joy.",
    }
    hass.bus.async_fire(EVENT_NEW_QUOTE_FETCHED, quote_2)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    quotes = literal_eval(state.attributes[ATTR_QUOTES])
    assert len(quotes) == 2
    assert quotes[0] == quote_2
