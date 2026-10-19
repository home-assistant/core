"""Compatibility imports for the Home Assistant pytest helpers."""

# ruff: noqa: PLC0414

from pytest_homeassistant.test_util.aiohttp import (
    EVENT_HOMEASSISTANT_CLOSE as EVENT_HOMEASSISTANT_CLOSE,
    RETYPE as RETYPE,
    URL as URL,
    AiohttpClientMocker as AiohttpClientMocker,
    AiohttpClientMockResponse as AiohttpClientMockResponse,
    Any as Any,
    CIMultiDict as CIMultiDict,
    ClientConnectionError as ClientConnectionError,
    ClientError as ClientError,
    ClientResponseError as ClientResponseError,
    ClientSession as ClientSession,
    HomeAssistant as HomeAssistant,
    HTTPStatus as HTTPStatus,
    Iterator as Iterator,
    MockLongPollSideEffect as MockLongPollSideEffect,
    StreamReader as StreamReader,
    TracebackType as TracebackType,
    asyncio as asyncio,
    contextmanager as contextmanager,
    json_dumps as json_dumps,
    json_loads as json_loads,
    mock as mock,
    mock_aiohttp_client as mock_aiohttp_client,
    mock_stream as mock_stream,
    parse_qs as parse_qs,
    re as re,
)
