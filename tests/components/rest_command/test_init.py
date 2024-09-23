"""The tests for the rest command platform."""

import base64
from http import HTTPStatus
from unittest.mock import patch

import aiohttp
import pytest

from homeassistant.components.rest_command import DOMAIN
from homeassistant.const import (
    CONTENT_TYPE_JSON,
    CONTENT_TYPE_TEXT_PLAIN,
    SERVICE_RELOAD,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import TEST_URL, ComponentSetup

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_reload(hass: HomeAssistant, setup_component: ComponentSetup) -> None:
    """Verify we can reload rest_command integration."""
    await setup_component()

    assert hass.services.has_service(DOMAIN, "get_test")
    assert not hass.services.has_service(DOMAIN, "new_test")

    new_config = {
        DOMAIN: {
            "new_test": {"url": "https://example.org", "method": "get"},
        }
    }
    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value=new_config,
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)

    assert hass.services.has_service(DOMAIN, "new_test")
    assert not hass.services.has_service(DOMAIN, "get_test")


async def test_setup_tests(
    hass: HomeAssistant, setup_component: ComponentSetup
) -> None:
    """Set up test config and test it."""
    await setup_component()

    assert hass.services.has_service(DOMAIN, "get_test")
    assert hass.services.has_service(DOMAIN, "post_test")
    assert hass.services.has_service(DOMAIN, "put_test")
    assert hass.services.has_service(DOMAIN, "delete_test")


async def test_rest_command_timeout(
    hass: HomeAssistant,
    setup_component: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Call a rest command with timeout."""
    await setup_component()

    aioclient_mock.get(TEST_URL, exc=TimeoutError())

    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(DOMAIN, "get_test", {}, blocking=True)
    assert str(exc.value) == 'Timeout when calling resource "https://example.com/"'

    assert len(aioclient_mock.mock_calls) == 1


async def test_rest_command_aiohttp_error(
    hass: HomeAssistant,
    setup_component: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Call a rest command with aiohttp exception."""
    await setup_component()

    aioclient_mock.get(TEST_URL, exc=aiohttp.ClientError())

    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(DOMAIN, "get_test", {}, blocking=True)

    assert (
        str(exc.value)
        == 'Client error occurred when calling resource "https://example.com/"'
    )
    assert len(aioclient_mock.mock_calls) == 1


async def test_rest_command_http_error(
    hass: HomeAssistant,
    setup_component: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Call a rest command with status code 400."""
    await setup_component()

    aioclient_mock.get(TEST_URL, status=HTTPStatus.BAD_REQUEST)

    await hass.services.async_call(DOMAIN, "get_test", {}, blocking=True)

    assert len(aioclient_mock.mock_calls) == 1


async def test_rest_command_auth(
    hass: HomeAssistant,
    setup_component: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Call a rest command with auth credential."""
    await setup_component()

    aioclient_mock.get(TEST_URL, content=b"success")

    await hass.services.async_call(DOMAIN, "auth_test", {}, blocking=True)

    assert len(aioclient_mock.mock_calls) == 1


async def test_rest_command_form_data(
    hass: HomeAssistant,
    setup_component: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Call a rest command with post form data."""
    await setup_component()

    aioclient_mock.post(TEST_URL, content=b"success")

    await hass.services.async_call(DOMAIN, "post_test", {}, blocking=True)

    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == b"test"


@pytest.mark.parametrize(
    "method",
    [
        "get",
        "patch",
        "post",
        "put",
        "delete",
    ],
)
async def test_rest_command_methods(
    hass: HomeAssistant,
    setup_component: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    method: str,
) -> None:
    """Test various http methods."""
    await setup_component()

    aioclient_mock.request(method=method, url=TEST_URL, content=b"success")

    await hass.services.async_call(DOMAIN, f"{method}_test", {}, blocking=True)

    assert len(aioclient_mock.mock_calls) == 1


async def test_rest_command_headers(
    hass: HomeAssistant,
    setup_component: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Call a rest command with custom headers and content types."""
    header_config_variations = {
        "no_headers_test": {},
        "content_type_test": {"content_type": CONTENT_TYPE_TEXT_PLAIN},
        "headers_test": {
            "headers": {
                "Accept": CONTENT_TYPE_JSON,
                "User-Agent": "Mozilla/5.0",
            }
        },
        "headers_and_content_type_test": {
            "headers": {"Accept": CONTENT_TYPE_JSON},
            "content_type": CONTENT_TYPE_TEXT_PLAIN,
        },
        "headers_and_content_type_override_test": {
            "headers": {
                "Accept": CONTENT_TYPE_JSON,
                aiohttp.hdrs.CONTENT_TYPE: "application/pdf",
            },
            "content_type": CONTENT_TYPE_TEXT_PLAIN,
        },
        "headers_template_test": {
            "headers": {
                "Accept": CONTENT_TYPE_JSON,
                "User-Agent": "Mozilla/{{ 3 + 2 }}.0",
            }
        },
        "headers_and_content_type_override_template_test": {
            "headers": {
                "Accept": "application/{{ 1 + 1 }}json",
                aiohttp.hdrs.CONTENT_TYPE: "application/pdf",
            },
            "content_type": "text/json",
        },
    }

    # add common parameters
    for variation in header_config_variations.values():
        variation.update({"url": TEST_URL, "method": "post", "payload": "test data"})

    await setup_component(header_config_variations)

    # provide post request data
    aioclient_mock.post(TEST_URL, content=b"success")

    for test_service in (
        "no_headers_test",
        "content_type_test",
        "headers_test",
        "headers_and_content_type_test",
        "headers_and_content_type_override_test",
        "headers_template_test",
        "headers_and_content_type_override_template_test",
    ):
        await hass.services.async_call(DOMAIN, test_service, {}, blocking=True)

    await hass.async_block_till_done()
    assert len(aioclient_mock.mock_calls) == 7

    # no_headers_test
    assert aioclient_mock.mock_calls[0][3] is None

    # content_type_test
    assert len(aioclient_mock.mock_calls[1][3]) == 1
    assert (
        aioclient_mock.mock_calls[1][3].get(aiohttp.hdrs.CONTENT_TYPE)
        == CONTENT_TYPE_TEXT_PLAIN
    )

    # headers_test
    assert len(aioclient_mock.mock_calls[2][3]) == 2
    assert aioclient_mock.mock_calls[2][3].get("Accept") == CONTENT_TYPE_JSON
    assert aioclient_mock.mock_calls[2][3].get("User-Agent") == "Mozilla/5.0"

    # headers_and_content_type_test
    assert len(aioclient_mock.mock_calls[3][3]) == 2
    assert (
        aioclient_mock.mock_calls[3][3].get(aiohttp.hdrs.CONTENT_TYPE)
        == CONTENT_TYPE_TEXT_PLAIN
    )
    assert aioclient_mock.mock_calls[3][3].get("Accept") == CONTENT_TYPE_JSON

    # headers_and_content_type_override_test
    assert len(aioclient_mock.mock_calls[4][3]) == 2
    assert (
        aioclient_mock.mock_calls[4][3].get(aiohttp.hdrs.CONTENT_TYPE)
        == CONTENT_TYPE_TEXT_PLAIN
    )
    assert aioclient_mock.mock_calls[4][3].get("Accept") == CONTENT_TYPE_JSON

    # headers_template_test
    assert len(aioclient_mock.mock_calls[5][3]) == 2
    assert aioclient_mock.mock_calls[5][3].get("Accept") == CONTENT_TYPE_JSON
    assert aioclient_mock.mock_calls[5][3].get("User-Agent") == "Mozilla/5.0"

    # headers_and_content_type_override_template_test
    assert len(aioclient_mock.mock_calls[6][3]) == 2
    assert aioclient_mock.mock_calls[6][3].get(aiohttp.hdrs.CONTENT_TYPE) == "text/json"
    assert aioclient_mock.mock_calls[6][3].get("Accept") == "application/2json"


async def test_rest_command_get_response_plaintext(
    hass: HomeAssistant,
    setup_component: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Get rest_command response, text."""
    await setup_component()

    aioclient_mock.get(
        TEST_URL, content=b"success", headers={"content-type": "text/plain"}
    )

    response = await hass.services.async_call(
        DOMAIN, "get_test", {}, blocking=True, return_response=True
    )

    assert len(aioclient_mock.mock_calls) == 1
    assert response["content"] == "success"
    assert response["status"] == 200


async def test_rest_command_get_response_json(
    hass: HomeAssistant,
    setup_component: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Get rest_command response, json."""
    await setup_component()

    aioclient_mock.get(
        TEST_URL,
        json={"status": "success", "number": 42},
        headers={"content-type": "application/json"},
    )

    response = await hass.services.async_call(
        DOMAIN, "get_test", {}, blocking=True, return_response=True
    )

    assert len(aioclient_mock.mock_calls) == 1
    assert response["content"]["status"] == "success"
    assert response["content"]["number"] == 42
    assert response["status"] == 200


async def test_rest_command_get_response_malformed_json(
    hass: HomeAssistant,
    setup_component: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Get rest_command response, malformed json."""
    await setup_component()

    aioclient_mock.get(
        TEST_URL,
        content='{"status": "failure", 42',
        headers={"content-type": "application/json"},
    )

    # No problem without 'return_response'
    response = await hass.services.async_call(DOMAIN, "get_test", {}, blocking=True)
    assert not response

    # Throws error when requesting response
    with pytest.raises(HomeAssistantError) as exc:
        await hass.services.async_call(
            DOMAIN, "get_test", {}, blocking=True, return_response=True
        )
    assert (
        str(exc.value)
        == 'The response of "https://example.com/" could not be decoded as JSON'
    )


async def test_rest_command_get_response_none(
    hass: HomeAssistant,
    setup_component: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Get rest_command response, other."""
    await setup_component()

    png = base64.decodebytes(
        b"iVBORw0KGgoAAAANSUhEUgAAAAIAAAABCAIAAAB7QOjdAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQ"
        b"UAAAAJcEhZcwAAFiUAABYlAUlSJPAAAAAPSURBVBhXY/h/ku////8AECAE1JZPvDAAAAAASUVORK5CYII="
    )

    aioclient_mock.get(
        TEST_URL,
        content=png,
        headers={"content-type": "text/plain"},
    )

    # No problem without 'return_response'
    response = await hass.services.async_call(DOMAIN, "get_test", {}, blocking=True)
    assert not response

    # Throws Decode error when requesting response
    with pytest.raises(HomeAssistantError) as exc:
        response = await hass.services.async_call(
            DOMAIN, "get_test", {}, blocking=True, return_response=True
        )
    assert (
        str(exc.value)
        == 'The response of "https://example.com/" could not be decoded as text'
    )

    assert not response
