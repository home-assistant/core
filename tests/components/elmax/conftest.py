"""Configuration for Elmax tests."""
import json

from elmax_api.constants import (
    BASE_URL,
    ENDPOINT_DEVICES,
    ENDPOINT_DISCOVERY,
    ENDPOINT_LOGIN,
)
from httpx import Response
import pytest
import respx

from tests.common import load_fixture
from tests.components.elmax import MOCK_PANEL_ID, MOCK_PANEL_PIN


@pytest.fixture(autouse=True)
def httpx_mock_fixture(requests_mock):
    """Configure httpx fixture."""
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as respx_mock:
        # Mock Login POST.
        login_route = respx_mock.post(f"/{ENDPOINT_LOGIN}", name="login")
        login_route.return_value = Response(
            200, json=json.loads(load_fixture("login.json", "elmax"))
        )

        # Mock Device list GET.
        list_devices_route = respx_mock.get(f"/{ENDPOINT_DEVICES}", name="list_devices")
        list_devices_route.return_value = Response(
            200, json=json.loads(load_fixture("list_devices.json", "elmax"))
        )

        # Mock Panel GET.
        get_panel_route = respx_mock.get(
            f"/{ENDPOINT_DISCOVERY}/{MOCK_PANEL_ID}/{MOCK_PANEL_PIN}", name="get_panel"
        )
        get_panel_route.return_value = Response(
            200, json=json.loads(load_fixture("get_panel.json", "elmax"))
        )

        yield respx_mock
