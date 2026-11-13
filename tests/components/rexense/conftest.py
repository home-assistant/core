"""Fixtures at the public aiorexense boundary."""

from collections.abc import Generator
from copy import deepcopy
from unittest.mock import MagicMock, patch

from aiorexense import Endpoint
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.rexense.const import DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)

GATEWAY_ID = "rexense-gateway"
MAC = "00124B0000000001"
ADDRESS = f"{MAC}:1"
INFO = {
    "code": 0,
    "taxonomy_version": 3,
    "system": {"sn": GATEWAY_ID, "model": "RG5100", "sw_version": "4.0.0"},
}
CONNECTION = {
    CONF_HOST: "192.0.2.1",
    CONF_PORT: 8090,
    CONF_API_KEY: "",
    CONF_SSL: False,
    CONF_VERIFY_SSL: True,
}


@pytest.fixture
def mock_client() -> Generator[MagicMock]:
    """Mock the SDK's short-lived connection test."""
    with patch(
        "homeassistant.components.rexense.config_flow.RexenseClient", autospec=True
    ) as factory:
        client = factory.return_value
        client.async_connect.return_value = deepcopy(INFO)
        yield client


@pytest.fixture
def endpoint() -> Endpoint:
    """Return an observed switch with confirmed on/off capabilities."""
    return Endpoint(
        addr=ADDRESS,
        node={
            "mac": MAC,
            "model_id": "TL0001",
            "mfg_name": "Rexense",
            "sw_build_id": "20260630 17:12",
        },
        metadata={"dev_type": "switch", "endpoint": 1},
        definitions={
            "onoff": {
                "properties": {"on": {"type": "bool", "access": "rw"}},
                "actions": {},
                "events": {},
            }
        },
        properties={"on": True},
        state="online",
        confirmed=True,
    )


@pytest.fixture
def mock_gateway(endpoint: Endpoint) -> Generator[MagicMock]:
    """Mock the library's public gateway and push subscription."""
    with patch(
        "homeassistant.components.rexense.RexenseGateway", autospec=True
    ) as factory:
        gateway = factory.return_value
        gateway.connected = True
        gateway.unique_id = GATEWAY_ID
        gateway.gateway = deepcopy(INFO)
        gateway.endpoints = {ADDRESS: endpoint}
        yield gateway


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a previously configured gateway."""
    return MockConfigEntry(
        domain=DOMAIN, title="Rexense RG5100", unique_id=GATEWAY_ID, data=CONNECTION
    )
