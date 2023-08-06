"""Fixtures for BMW tests."""


from collections.abc import Generator
from unittest.mock import Mock

from bimmer_connected.tests import ALL_CHARGING_SETTINGS, ALL_STATES
from bimmer_connected.tests.common import MyBMWMockRouter
from bimmer_connected.vehicle import remote_services
import pytest
import respx

from homeassistant.components.bmw_connected_drive.coordinator import (
    BMWDataUpdateCoordinator,
)


@pytest.fixture
def bmw_fixture(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Generator[respx.MockRouter, None, None]:
    """Patch MyBMW login API calls."""

    # we use the library's mock router to mock the API calls, but only with a subset of vehicles
    router = MyBMWMockRouter(
        vehicles_to_load=[
            "WBA00000000DEMO01",
            "WBA00000000DEMO02",
            "WBA00000000DEMO03",
            "WBY00000000REXI01",
        ],
        states=ALL_STATES,
        charging_settings=ALL_CHARGING_SETTINGS,
    )

    # we don't want to wait when triggering a remote service
    monkeypatch.setattr(
        remote_services,
        "_POLLING_CYCLE",
        0,
    )

    # needed to check if the coordinator update is triggered
    monkeypatch.setattr(
        BMWDataUpdateCoordinator,
        "async_update_listeners",
        Mock(),
    )

    with router:
        yield router
