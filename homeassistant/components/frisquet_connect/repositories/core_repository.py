import logging
import aiohttp
from frisquet_connect.domains.exceptions.call_api_exception import (
    CallApiException,
)
from frisquet_connect.domains.exceptions.forbidden_access_exception import (
    ForbiddenAccessException,
)


_LOGGER = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "okhttp/4.12.0"

DEFAULT_HEADERS = {
    "Accept-Encoding": "gzip",
    "Accept-Language": "FR",
    "Android-Version": "2.8.1",
    "User-Agent": DEFAULT_USER_AGENT,
    "Connection": "keep-alive",
}


async def _async_call_api(
    url, method: str, params: dict = None, data_json: dict = None
) -> dict:
    """
    Makes an HTTP request to the specified URL using the given method and data.
    Args:
        url (str): The URL to which the request is to be made.
        method (str, optional): The HTTP method to use for the request. Defaults to "GET".
        data (dict, optional): The data to send with the request, if applicable. Defaults to None.
    Returns:
        dict: The JSON response resulting from the HTTP request.
    """
    _LOGGER.debug(f"Calling API: {method} {url}")
    headers = DEFAULT_HEADERS.copy()
    async with aiohttp.ClientSession(headers=DEFAULT_HEADERS) as session:
        try:
            if method == "GET":
                response = await session.get(
                    url, headers=DEFAULT_HEADERS, params=params
                )
            elif method == "POST":
                headers["Content-Type"] = "application/json"
                response = await session.post(
                    url, headers=DEFAULT_HEADERS, params=params, json=data_json
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            _LOGGER.debug(f"API called with url: {response.request_info.url}")
            response.raise_for_status()
            return await response.json()
        except aiohttp.ClientResponseError as e:
            error_message = f"API call failed: {e.status} - {e.message}"
            class_exception = CallApiException

            if e.status == 403:
                class_exception = ForbiddenAccessException
                _LOGGER.warning(error_message)
            else:
                _LOGGER.error(error_message)
            raise class_exception(error_message)


async def async_do_websocket(url: str, params: dict, data_json: dict = None) -> None:
    """
    Makes a WebSocket request to the specified URL using the given parameters.
    Args:
        url (str): The URL to which the request is to be made.
        params (dict): The parameters to send with the request.
    Returns:
        dict: The JSON response resulting from the WebSocket request.
    """
    _LOGGER.debug(f"Calling WebSocket API: {url}")

    async with aiohttp.ClientSession() as session:
        try:
            count = 0
            ws = await session.ws_connect(url, params=params)
            await ws.send_json(data_json)
            while count < 10:
                count += 1
                _LOGGER.debug(f"WebSocket waiting for response {count}/10")

                ws_response_json = await ws.receive_json(timeout=300)
                if ws_response_json.get("type") == "ORDRE_OK":
                    _LOGGER.info(f"WebSocket expected response: {ws_response_json}")
                    await ws.close()
                    return
                else:
                    _LOGGER.debug(f"WebSocket other response: {ws_response_json}")

            await ws.close()
            raise CallApiException("WebSocket response timeout")

        except aiohttp.ClientResponseError as e:
            error_message = f"WebSocket call failed: {e.status} - {e.message}"
            raise CallApiException(error_message)


async def async_do_get(url: str, params: dict) -> dict:
    return await _async_call_api(url, "GET", params)


async def async_do_post(url: str, params: dict, data: dict) -> dict:
    return await _async_call_api(url, "POST", params, data)
