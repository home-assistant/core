"""Configuration for Elmax tests."""

from collections.abc import Generator
from datetime import datetime, timedelta
import json
from unittest.mock import AsyncMock, patch

from elmax_api.constants import (
    BASE_URL,
    ENDPOINT_DEVICES,
    ENDPOINT_DISCOVERY,
    ENDPOINT_LOGIN,
)
from httpx import Response
import jwt
import pytest
import respx

from . import (
    MOCK_DIRECT_HOST,
    MOCK_DIRECT_PORT,
    MOCK_DIRECT_SSL,
    MOCK_PANEL_ID,
    MOCK_PANEL_PIN,
)

from tests.common import load_fixture

MOCK_DIRECT_BASE_URI = (
    f"{'https' if MOCK_DIRECT_SSL else 'http'}://{MOCK_DIRECT_HOST}:{MOCK_DIRECT_PORT}"
)


@pytest.fixture(autouse=True)
def httpx_mock_cloud_fixture() -> Generator[respx.MockRouter]:
    """Configure httpx fixture for cloud API communication."""
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as respx_mock:
        # Mock Login POST.
        login_route = respx_mock.post(f"/{ENDPOINT_LOGIN}", name="login")
        login_route.return_value = Response(
            200, json=json.loads(load_fixture("cloud/login.json", "elmax"))
        )

        # Mock Device list GET.
        list_devices_route = respx_mock.get(f"/{ENDPOINT_DEVICES}", name="list_devices")
        list_devices_route.return_value = Response(
            200, json=json.loads(load_fixture("cloud/list_devices.json", "elmax"))
        )

        # Mock Panel GET.
        get_panel_route = respx_mock.get(
            f"/{ENDPOINT_DISCOVERY}/{MOCK_PANEL_ID}/{MOCK_PANEL_PIN}", name="get_panel"
        )
        get_panel_route.return_value = Response(
            200, json=json.loads(load_fixture("cloud/get_panel.json", "elmax"))
        )

        yield respx_mock


@pytest.fixture(autouse=True)
def httpx_mock_direct_fixture() -> Generator[respx.MockRouter]:
    """Configure httpx fixture for direct Panel-API communication."""
    with respx.mock(
        base_url=MOCK_DIRECT_BASE_URI, assert_all_called=False
    ) as respx_mock:
        # Mock Login POST.
        login_route = respx_mock.post(f"/api/v2/{ENDPOINT_LOGIN}", name="login")

        login_json = json.loads(load_fixture("direct/login.json", "elmax"))
        decoded_jwt = jwt.decode_complete(
            login_json["token"].split(" ")[1],
            algorithms="HS256",
            options={"verify_signature": False},
        )
        expiration = datetime.now() + timedelta(hours=1)
        decoded_jwt["payload"]["exp"] = int(expiration.timestamp())
        jws_string = jwt.encode(
            payload=decoded_jwt["payload"], algorithm="HS256", key=""
        )
        login_json["token"] = f"JWT {jws_string}"
        login_route.return_value = Response(200, json=login_json)

        # Mock Device list GET.
        list_devices_route = respx_mock.get(
            f"/api/v2/{ENDPOINT_DISCOVERY}", name="discovery_panel"
        )
        list_devices_route.return_value = Response(
            200, json=json.loads(load_fixture("direct/discovery_panel.json", "elmax"))
        )

        yield respx_mock


@pytest.fixture(autouse=True)
def elmax_mock_direct_cert() -> Generator[AsyncMock]:
    """Patch elmax library to return a specific PEM for SSL communication."""
    with patch(
        "elmax_api.http.GenericElmax.retrieve_server_certificate",
        return_value=load_fixture("direct/cert.pem", "elmax"),
    ) as patched_ssl_get_cert:
        yield patched_ssl_get_cert
