"""Unit tests for template functions."""

from homeassistant.components import jewish_calendar
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template
from homeassistant.setup import async_setup_component


async def test_get_hebrew_date_string_date(hass: HomeAssistant) -> None:
    """Tests get_hebrew_date."""
    assert await async_setup_component(
        hass, jewish_calendar.DOMAIN, {"jewish_calendar": {"language": "hebrew"}}
    )
    await hass.async_block_till_done()

    assert (
        Template("{{ get_hebrew_date('2020-02-02').daf_yomi }}", hass).async_render()
        == "ברכות ל"
    )


async def test_get_hebrew_date_timestamp(hass: HomeAssistant) -> None:
    """Tests get_hebrew_date."""
    assert await async_setup_component(
        hass, jewish_calendar.DOMAIN, {"jewish_calendar": {"language": "english"}}
    )
    await hass.async_block_till_done()

    assert (
        Template("{{ get_hebrew_date(9876543210) | string }}", hass).async_render()
        == "Friday 20 Kislev 6043"
    )


async def test_get_hebrew_date_date(hass: HomeAssistant) -> None:
    """Tests get_hebrew_date."""
    assert await async_setup_component(
        hass, jewish_calendar.DOMAIN, {"jewish_calendar": {"language": "english"}}
    )
    await hass.async_block_till_done()

    assert (
        Template(
            "{{ '2020-02-02' | as_datetime | get_hebrew_date | string }}", hass
        ).async_render()
        == "Sunday 7 Sh'vat 5780"
    )


async def test_get_zmanim(hass: HomeAssistant) -> None:
    """Tests get_zmanim."""
    assert await async_setup_component(
        hass,
        jewish_calendar.DOMAIN,
        {"jewish_calendar": {"language": "english", "diaspora": "true"}},
    )
    await hass.async_block_till_done()

    assert (
        Template(
            "{{ get_zmanim('2023-10-01').havdalah | as_timestamp | timestamp_utc }}",
            hass,
        ).async_render()
        == "2023-10-02T02:10:00+00:00"
    )
