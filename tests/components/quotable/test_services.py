"""Test the Quotable integration services."""


import aiohttp

from homeassistant.components.quotable.const import (
    ATTR_AUTHOR,
    ATTR_BG_COLOR,
    ATTR_CONTENT,
    ATTR_DATA,
    ATTR_ERROR,
    ATTR_NAME,
    ATTR_SELECTED_AUTHORS,
    ATTR_SELECTED_TAGS,
    ATTR_SLUG,
    ATTR_STYLES,
    ATTR_SUCCESS,
    ATTR_TEXT_COLOR,
    ATTR_UPDATE_FREQUENCY,
    DOMAIN,
    ERROR_FETCHING_DATA_FROM_QUOTABLE_API,
    ERROR_MISSING_SEARCH_QUERY,
    FETCH_A_QUOTE_URL,
    GET_AUTHORS_URL,
    GET_TAGS_URL,
    SEARCH_AUTHORS_URL,
    SERVICE_FETCH_A_QUOTE,
    SERVICE_FETCH_ALL_AUTHORS,
    SERVICE_FETCH_ALL_TAGS,
    SERVICE_SEARCH_AUTHORS,
    SERVICE_UPDATE_CONFIGURATION,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_services_correctly_registered(hass: HomeAssistant) -> None:
    """Test that all the services are correctly registered."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_FETCH_A_QUOTE)
    assert hass.services.has_service(DOMAIN, SERVICE_FETCH_ALL_AUTHORS)
    assert hass.services.has_service(DOMAIN, SERVICE_FETCH_ALL_TAGS)
    assert hass.services.has_service(DOMAIN, SERVICE_SEARCH_AUTHORS)
    assert hass.services.has_service(DOMAIN, SERVICE_UPDATE_CONFIGURATION)


async def test_fetch_all_tags_service_returns_error_response_when_exception_is_thrown(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The fetch_all_tags service must return an error response when an exception is thrown while fetching/parsing data from the Quotable API."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    aioclient_mock.get(GET_TAGS_URL, exc=aiohttp.ClientError)

    service_response = await hass.services.async_call(
        DOMAIN,
        SERVICE_FETCH_ALL_TAGS,
        blocking=True,
        return_response=True,
    )

    assert not service_response.get(ATTR_SUCCESS)
    assert service_response.get(ATTR_ERROR) == ERROR_FETCHING_DATA_FROM_QUOTABLE_API


async def test_fetch_all_tags_service_success_response(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The fetch_all_tags service must return a success response when data is successfully fetched/parsed from the Quotable API."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    mock_tags = [
        {
            ATTR_NAME: "Love",
            ATTR_SLUG: "love",
        },
        {
            ATTR_NAME: "Peace",
            ATTR_SLUG: "peace",
        },
    ]

    aioclient_mock.get(
        GET_TAGS_URL,
        json=mock_tags,
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_FETCH_ALL_TAGS,
        blocking=True,
        return_response=True,
    )

    assert response.get(ATTR_SUCCESS)
    assert response.get(ATTR_DATA) == mock_tags


async def test_fetch_all_authors_service_returns_error_response_when_exception_is_thrown(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The fetch_all_authors service must return an error response when an exception is thrown while fetching/parsing data from the Quotable API."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    aioclient_mock.get(GET_AUTHORS_URL, exc=aiohttp.ClientError)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_FETCH_ALL_AUTHORS,
        blocking=True,
        return_response=True,
    )

    assert not response.get(ATTR_SUCCESS)
    assert response.get(ATTR_ERROR) == ERROR_FETCHING_DATA_FROM_QUOTABLE_API


async def test_fetch_all_authors_service_success_response(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test fetch_all_authors service returns success response."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    mock_authors = [
        {
            ATTR_NAME: "Albert Einstein",
            ATTR_SLUG: "albert-einstein",
        },
        {
            ATTR_NAME: "Rumi",
            ATTR_SLUG: "rumi",
        },
    ]

    aioclient_mock.get(
        GET_AUTHORS_URL,
        json={"results": mock_authors},
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_FETCH_ALL_AUTHORS,
        blocking=True,
        return_response=True,
    )

    assert response.get(ATTR_SUCCESS)
    assert response.get(ATTR_DATA) == mock_authors


async def test_search_authors_service_returns_error_response_when_search_query_is_missing(
    hass: HomeAssistant,
) -> None:
    """The search_authors service must return error an response when the search query is missing in the service call."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH_AUTHORS,
        blocking=True,
        return_response=True,
    )

    assert not response.get(ATTR_SUCCESS)
    assert response.get(ATTR_ERROR) == ERROR_MISSING_SEARCH_QUERY


async def test_search_authors_service_returns_error_response_when_exception_is_thrown(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The search_authors service must return an error response when an exception is thrown while fetching/parsing data from the Quotable API."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    aioclient_mock.get(SEARCH_AUTHORS_URL, exc=aiohttp.ClientError)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH_AUTHORS,
        service_data={"query": "albert"},
        blocking=True,
        return_response=True,
    )

    assert not response.get(ATTR_SUCCESS)
    assert response.get(ATTR_ERROR) == ERROR_FETCHING_DATA_FROM_QUOTABLE_API


async def test_search_authors_service_success_response(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test search_authors service must return a success response when data is successfully fetched/parsed from the Quotable API."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    mock_authors = [
        {
            ATTR_NAME: "Albert Einstein",
            ATTR_SLUG: "albert-einstein",
        }
    ]

    aioclient_mock.get(
        SEARCH_AUTHORS_URL,
        json={"results": mock_authors},
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SEARCH_AUTHORS,
        service_data={"query": "albert"},
        blocking=True,
        return_response=True,
    )

    assert response.get(ATTR_SUCCESS)
    assert response.get(ATTR_DATA) == mock_authors


async def test_fetch_a_quote_service_returns_error_response_when_exception_is_thrown(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The fetch_a_quote service must return an error response when an exception is thrown while fetching/parsing data from the Quotable API."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    aioclient_mock.get(FETCH_A_QUOTE_URL, exc=aiohttp.ClientError)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_FETCH_A_QUOTE,
        blocking=True,
        return_response=True,
    )

    assert not response.get(ATTR_SUCCESS)
    assert response.get(ATTR_ERROR) == ERROR_FETCHING_DATA_FROM_QUOTABLE_API


async def test_fetch_a_quote_service_success_response(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The fetch_a_quote service must return a success response when data is successfully fetched/parsed from the Quotable API."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    quote = {
        ATTR_AUTHOR: "Rumi",
        ATTR_CONTENT: "Patience is the key to joy.",
    }

    aioclient_mock.get(
        FETCH_A_QUOTE_URL,
        json=[quote],
    )

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_FETCH_A_QUOTE,
        blocking=True,
        return_response=True,
    )

    assert response.get(ATTR_SUCCESS)
    assert response.get(ATTR_DATA) == quote


async def test_update_configuration_service(hass: HomeAssistant) -> None:
    """The update_configuration service must update the configuration values in the global hass object for the quotable intgration."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    selected_tags = ["science", "love"]
    selected_authors = ["albert-einstien", "rumi"]
    update_frequency = 30
    styles = {ATTR_BG_COLOR: "#000", ATTR_TEXT_COLOR: "#fff"}

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_CONFIGURATION,
        service_data={
            ATTR_SELECTED_TAGS: selected_tags,
            ATTR_SELECTED_AUTHORS: selected_authors,
            ATTR_UPDATE_FREQUENCY: update_frequency,
            ATTR_STYLES: styles,
        },
    )
    await hass.async_block_till_done()

    quotable = hass.data.get(DOMAIN)

    assert quotable.config[ATTR_SELECTED_TAGS] == selected_tags
    assert quotable.config[ATTR_SELECTED_AUTHORS] == selected_authors
    assert quotable.config[ATTR_UPDATE_FREQUENCY] == update_frequency
    assert quotable.config[ATTR_STYLES] == styles
