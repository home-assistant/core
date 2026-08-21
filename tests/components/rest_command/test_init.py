"""The tests for the rest command platform."""

import base64
from collections.abc import AsyncIterator
from http import HTTPStatus
import logging
from unittest.mock import MagicMock, patch

import aiohttp
from multidict import CIMultiDict
import pytest
import voluptuous as vol
from yarl import URL

from homeassistant.components.rest_command import CONFIG_SCHEMA
from homeassistant.components.rest_command.const import (
    AUTHENTICATION_BEARER,
    AUTHENTICATION_NONE,
    CONF_INSECURE_CIPHER,
    CONF_SKIP_URL_ENCODING,
    DOMAIN,
    SERVICE_CALL_ENDPOINT,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_CONFIG_ENTRY_ID,
    CONF_AUTHENTICATION,
    CONF_METHOD,
    CONF_PASSWORD,
    CONF_PAYLOAD,
    CONF_TIMEOUT,
    CONF_TOKEN,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONTENT_TYPE_JSON,
    CONTENT_TYPE_TEXT_PLAIN,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
    SERVICE_RELOAD,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import TEST_URL, ComponentSetup

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


def _configure_mock_response(mock_request: MagicMock, url: str = TEST_URL) -> None:
    """Configure a mocked aiohttp request context manager."""

    async def async_iter_chunks(self: object, chunk_size: int) -> AsyncIterator[bytes]:
        yield b"success"

    mock_request.return_value.__aenter__.return_value = type(
        "MockResponse",
        (),
        {
            "status": 200,
            "content_type": "text/plain",
            "headers": {},
            "url": url,
            "content": type("MockContent", (), {"iter_chunked": async_iter_chunks})(),
        },
    )()


async def test_reserved_yaml_action_name() -> None:
    """Test integration-owned action names are rejected in YAML."""
    with pytest.raises(
        vol.Invalid,
        match=rf'The RESTful Command action name "{SERVICE_RELOAD}" is reserved',
    ):
        CONFIG_SCHEMA({DOMAIN: {SERVICE_RELOAD: {CONF_URL: TEST_URL}}})


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
    assert hass.services.has_service(DOMAIN, SERVICE_CALL_ENDPOINT)


async def test_yaml_call_endpoint_takes_precedence(
    hass: HomeAssistant, setup_component: ComponentSetup
) -> None:
    """Test an existing YAML call_endpoint action keeps working."""
    await setup_component(
        {
            SERVICE_CALL_ENDPOINT: {
                CONF_URL: TEST_URL,
                CONF_METHOD: "post",
                CONF_PAYLOAD: "{{ message }}",
            }
        }
    )

    with patch("aiohttp.ClientSession.post") as mock_post:
        _configure_mock_response(mock_post)
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CALL_ENDPOINT,
            {"message": "YAML payload"},
            blocking=True,
        )

    assert mock_post.call_args.kwargs["data"] == b"YAML payload"


async def test_reload_yaml_call_endpoint_ownership(
    hass: HomeAssistant, setup_component: ComponentSetup
) -> None:
    """Test reload gives an existing YAML call_endpoint action precedence."""
    await setup_component()
    collision_config = CONFIG_SCHEMA(
        {
            DOMAIN: {
                SERVICE_CALL_ENDPOINT: {
                    CONF_URL: TEST_URL,
                    CONF_METHOD: "post",
                    CONF_PAYLOAD: "{{ message }}",
                }
            }
        }
    )

    with patch(
        "homeassistant.components.rest_command.async_integration_yaml_config",
        autospec=True,
        return_value=collision_config,
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)

    with patch("aiohttp.ClientSession.post") as mock_post:
        _configure_mock_response(mock_post)
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CALL_ENDPOINT,
            {"message": "Reloaded YAML payload"},
            blocking=True,
        )

    assert mock_post.call_args.kwargs["data"] == b"Reloaded YAML payload"
    assert not hass.services.has_service(DOMAIN, "get_test")


async def test_reload_restores_ui_call_endpoint(
    hass: HomeAssistant,
    setup_component: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test removing the YAML collision restores the UI-managed action."""
    await setup_component(
        {SERVICE_CALL_ENDPOINT: {CONF_URL: TEST_URL, CONF_METHOD: "get"}}
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Example",
        data={
            CONF_URL: TEST_URL,
            CONF_METHOD: "get",
            CONF_AUTHENTICATION: AUTHENTICATION_NONE,
            CONF_TIMEOUT: 10,
            CONF_VERIFY_SSL: True,
            CONF_INSECURE_CIPHER: False,
            CONF_SKIP_URL_ENCODING: False,
        },
        unique_id="endpoint-id",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    with patch(
        "homeassistant.components.rest_command.async_integration_yaml_config",
        autospec=True,
        return_value=CONFIG_SCHEMA({DOMAIN: {}}),
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)

    aioclient_mock.get(TEST_URL, content=b"success")
    await hass.services.async_call(
        DOMAIN,
        SERVICE_CALL_ENDPOINT,
        {ATTR_CONFIG_ENTRY_ID: entry.entry_id},
        blocking=True,
    )

    assert len(aioclient_mock.mock_calls) == 1


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
    assert str(exc.value) == "Timeout when calling the RESTful Command endpoint"

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
        == "Client error occurred when calling the RESTful Command endpoint"
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


@pytest.mark.usefixtures("aioclient_mock")
async def test_rest_command_digest_auth(
    hass: HomeAssistant,
    setup_component: ComponentSetup,
) -> None:
    """Call a rest command with HTTP digest authentication."""
    config = {
        "digest_auth_test": {
            "url": TEST_URL,
            "method": "get",
            "username": "test_user",
            "password": "test_pass",
            "authentication": HTTP_DIGEST_AUTHENTICATION,
        }
    }

    await setup_component(config)

    with patch("aiohttp.ClientSession.get") as mock_get:

        async def async_iter_chunks(self, chunk_size: int):
            yield b"success"

        mock_response = type(
            "MockResponse",
            (),
            {
                "status": 200,
                "content_type": "text/plain",
                "headers": {},
                "url": TEST_URL,
                "content": type(
                    "MockContent", (), {"iter_chunked": async_iter_chunks}
                )(),
            },
        )()
        mock_get.return_value.__aenter__.return_value = mock_response

        await hass.services.async_call(DOMAIN, "digest_auth_test", {}, blocking=True)
        await hass.services.async_call(DOMAIN, "digest_auth_test", {}, blocking=True)

        assert len(mock_get.call_args_list) == 2
        first_middleware = mock_get.call_args_list[0].kwargs["middlewares"][0]
        second_middleware = mock_get.call_args_list[1].kwargs["middlewares"][0]
        assert isinstance(first_middleware, aiohttp.DigestAuthMiddleware)
        assert isinstance(second_middleware, aiohttp.DigestAuthMiddleware)
        assert first_middleware is not second_middleware


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
    assert response["headers"] == {"content-type": "text/plain"}


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
    assert response["headers"] == {"content-type": "application/json"}


async def test_rest_command_get_response_multiple_headers(
    hass: HomeAssistant,
    setup_component: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Get rest_command response with multiple headers of the same name."""
    await setup_component()

    aioclient_mock.get(
        TEST_URL,
        content=b"success",
        headers=CIMultiDict(
            [
                ("content-type", "text/plain"),
                ("set-cookie", "foo=bar; Path=/"),
                ("set-cookie", "baz=qux; Path=/"),
            ]
        ),
    )

    response = await hass.services.async_call(
        DOMAIN, "get_test", {}, blocking=True, return_response=True
    )

    assert len(aioclient_mock.mock_calls) == 1
    assert response["content"] == "success"
    assert response["status"] == 200
    assert response["headers"] == {
        "content-type": "text/plain",
        "set-cookie": ["foo=bar; Path=/", "baz=qux; Path=/"],
    }


async def test_rest_command_get_response_malformed_json(
    hass: HomeAssistant,
    setup_component: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Get rest_command response, malformed json."""
    await setup_component()

    aioclient_mock.get(
        TEST_URL,
        content=b'{"status": "failure", 42',
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
    assert str(exc.value) == "The RESTful Command response could not be decoded as JSON"


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
    assert str(exc.value) == "The RESTful Command response could not be decoded as text"

    assert not response


async def test_rest_command_response_iter_chunked(
    hass: HomeAssistant,
    setup_component: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Ensure response is consumed when return_response is False."""
    await setup_component()

    png = base64.decodebytes(
        b"iVBORw0KGgoAAAANSUhEUgAAAAIAAAABCAIAAAB7QOjdAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQ"
        b"UAAAAJcEhZcwAAFiUAABYlAUlSJPAAAAAPSURBVBhXY/h/ku////8AECAE1JZPvDAAAAAASUVORK5CYII="
    )
    aioclient_mock.get(TEST_URL, content=png)

    with patch("aiohttp.StreamReader.iter_chunked", autospec=True) as mock_iter_chunked:
        response = await hass.services.async_call(DOMAIN, "get_test", {}, blocking=True)

        # Ensure the response is not returned
        assert response is None

        # Verify iter_chunked was called with a chunk size
        assert mock_iter_chunked.called


async def test_rest_command_skip_url_encoding(
    hass: HomeAssistant,
    setup_component: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Check URL encoding."""
    config = {
        "skip_url_encoding_test": {
            "url": "0%2C",
            "method": "get",
            "skip_url_encoding": True,
        },
        "with_url_encoding_test": {
            "url": "1,",
            "method": "get",
        },
    }

    await setup_component(config)

    aioclient_mock.get(URL("0%2C", encoded=True), content=b"success")
    aioclient_mock.get(URL("1,"), content=b"success")

    await hass.services.async_call(DOMAIN, "skip_url_encoding_test", {}, blocking=True)
    await hass.services.async_call(DOMAIN, "with_url_encoding_test", {}, blocking=True)

    assert len(aioclient_mock.mock_calls) == 2
    assert str(aioclient_mock.mock_calls[0][1]) == "0%2C"
    assert str(aioclient_mock.mock_calls[1][1]) == "1,"


async def test_ui_managed_bearer_endpoint(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test calling a UI-managed endpoint with Bearer authentication."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Example",
        data={
            CONF_URL: TEST_URL,
            CONF_METHOD: "post",
            CONF_AUTHENTICATION: AUTHENTICATION_BEARER,
            CONF_TOKEN: "secret-token",
            CONF_PAYLOAD: "default payload",
            CONF_TIMEOUT: 10,
            CONF_VERIFY_SSL: True,
            CONF_INSECURE_CIPHER: False,
            CONF_SKIP_URL_ENCODING: False,
        },
        unique_id="endpoint-id",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    aioclient_mock.post(
        TEST_URL,
        content=b"success",
        headers={"content-type": "text/plain"},
    )
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_CALL_ENDPOINT,
        {
            ATTR_CONFIG_ENTRY_ID: entry.entry_id,
            CONF_PAYLOAD: "action payload",
        },
        blocking=True,
        return_response=True,
    )

    assert response == {
        "content": "success",
        "status": 200,
        "headers": {"content-type": "text/plain"},
    }
    assert aioclient_mock.mock_calls[0][2] == b"action payload"
    assert aioclient_mock.mock_calls[0][3]["Authorization"] == ("Bearer secret-token")

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CALL_ENDPOINT,
        {ATTR_CONFIG_ENTRY_ID: entry.entry_id},
        blocking=True,
    )

    assert aioclient_mock.mock_calls[1][2] == b"default payload"


async def test_ui_managed_basic_endpoint(hass: HomeAssistant) -> None:
    """Test UI-managed Basic authentication on the wire."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Basic endpoint",
        data={
            CONF_URL: TEST_URL,
            CONF_METHOD: "get",
            CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
            CONF_USERNAME: "basic-user",
            CONF_PASSWORD: "basic-password",
            CONF_TIMEOUT: 10,
            CONF_VERIFY_SSL: True,
            CONF_INSECURE_CIPHER: False,
            CONF_SKIP_URL_ENCODING: False,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    with patch("aiohttp.ClientSession.get") as mock_get:
        _configure_mock_response(mock_get)
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CALL_ENDPOINT,
            {ATTR_CONFIG_ENTRY_ID: entry.entry_id},
            blocking=True,
        )

    auth = mock_get.call_args.kwargs["auth"]
    assert isinstance(auth, aiohttp.BasicAuth)
    assert auth.login == "basic-user"
    assert auth.password == "basic-password"


async def test_ui_managed_digest_endpoint(hass: HomeAssistant) -> None:
    """Test UI-managed Digest authentication on the wire."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Digest endpoint",
        data={
            CONF_URL: TEST_URL,
            CONF_METHOD: "get",
            CONF_AUTHENTICATION: HTTP_DIGEST_AUTHENTICATION,
            CONF_USERNAME: "digest-user",
            CONF_PASSWORD: "digest-password",
            CONF_TIMEOUT: 10,
            CONF_VERIFY_SSL: True,
            CONF_INSECURE_CIPHER: False,
            CONF_SKIP_URL_ENCODING: False,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    with patch("aiohttp.ClientSession.get") as mock_get:
        _configure_mock_response(mock_get)
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CALL_ENDPOINT,
            {ATTR_CONFIG_ENTRY_ID: entry.entry_id},
            blocking=True,
        )

    middleware = mock_get.call_args.kwargs["middlewares"][0]
    assert isinstance(middleware, aiohttp.DigestAuthMiddleware)


async def test_loaded_reconfigure_updates_runtime_data(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a loaded entry uses reconfigured request data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Original endpoint",
        data={
            CONF_URL: TEST_URL,
            CONF_METHOD: "get",
            CONF_AUTHENTICATION: AUTHENTICATION_NONE,
            CONF_TIMEOUT: 10,
            CONF_VERIFY_SSL: True,
            CONF_INSECURE_CIPHER: False,
            CONF_SKIP_URL_ENCODING: False,
        },
        unique_id="endpoint-id",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    original_runtime_data = entry.runtime_data

    result = await entry.start_reconfigure_flow(hass)
    new_url = "https://example.org/reconfigured"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_URL: new_url,
            CONF_METHOD: "post",
            CONF_AUTHENTICATION: AUTHENTICATION_NONE,
            CONF_TIMEOUT: 15,
            CONF_VERIFY_SSL: True,
            CONF_INSECURE_CIPHER: False,
            CONF_SKIP_URL_ENCODING: False,
        },
    )
    await hass.async_block_till_done()

    assert result["reason"] == "reconfigure_successful"
    assert entry.state is ConfigEntryState.LOADED
    assert entry.title == "Original endpoint"
    assert entry.runtime_data is not original_runtime_data

    aioclient_mock.post(new_url, content=b"success")
    await hass.services.async_call(
        DOMAIN,
        SERVICE_CALL_ENDPOINT,
        {ATTR_CONFIG_ENTRY_ID: entry.entry_id},
        blocking=True,
    )

    assert aioclient_mock.mock_calls[0][0] == "POST"
    assert str(aioclient_mock.mock_calls[0][1]) == new_url


async def test_ui_managed_endpoint_unload(
    hass: HomeAssistant,
) -> None:
    """Test unloading a UI-managed endpoint."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: TEST_URL,
            CONF_METHOD: "get",
            CONF_AUTHENTICATION: "none",
            CONF_TIMEOUT: 10,
            CONF_VERIFY_SSL: True,
            CONF_INSECURE_CIPHER: False,
            CONF_SKIP_URL_ENCODING: False,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.services.has_service(DOMAIN, SERVICE_CALL_ENDPOINT)

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert hass.services.has_service(DOMAIN, SERVICE_CALL_ENDPOINT)

    with pytest.raises(ServiceValidationError, match="is not loaded"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CALL_ENDPOINT,
            {ATTR_CONFIG_ENTRY_ID: entry.entry_id},
            blocking=True,
        )


async def test_request_logging_redacts_secrets(
    hass: HomeAssistant,
    setup_component: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test rendered request secrets are not logged or included in errors."""
    secret_url = "https://example.com/hook?token=url-secret"
    await setup_component(
        {
            "secret_test": {
                "url": secret_url,
                "method": "post",
                "headers": {"Authorization": "Bearer header-secret"},
                "payload": "payload-secret",
            }
        }
    )
    aioclient_mock.post(secret_url, status=HTTPStatus.BAD_REQUEST)
    caplog.clear()

    with caplog.at_level(logging.DEBUG, logger="homeassistant.components.rest_command"):
        await hass.services.async_call(DOMAIN, "secret_test", {}, blocking=True)

    assert "url-secret" not in caplog.text
    assert "header-secret" not in caplog.text
    assert "payload-secret" not in caplog.text


async def test_client_error_redacts_exception(
    hass: HomeAssistant,
    setup_component: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test client exception details cannot expose request secrets."""
    await setup_component()
    aioclient_mock.get(TEST_URL, exc=aiohttp.ClientError("client-secret"))
    caplog.clear()

    with (
        caplog.at_level(logging.DEBUG, logger="homeassistant.components.rest_command"),
        pytest.raises(HomeAssistantError) as exc,
    ):
        await hass.services.async_call(DOMAIN, "get_test", {}, blocking=True)

    assert "client-secret" not in caplog.text
    assert "client-secret" not in str(exc.value)
    assert exc.value.__cause__ is None
