"""Tests for the WireGuard status API."""

from datetime import datetime as dt
import json
from unittest.mock import patch

import pytest
import requests

from homeassistant.components.wireguard.api import (
    WireGuardAPI,
    WireGuardError,
    WireGuardPeer,
    peer_from_data,
)
from homeassistant.components.wireguard.const import DEFAULT_HOST, DOMAIN

from .conftest import mocked_requests

from tests.common import load_fixture


def test_init() -> None:
    """Test for the initializer."""
    api = WireGuardAPI(DEFAULT_HOST)
    assert api.host == DEFAULT_HOST


@patch("requests.get", side_effect=mocked_requests)
def test_get_status_single_peer(mock_get) -> None:
    """Test get_status method."""
    api = WireGuardAPI("single_peer")
    status = api.get_status()

    assert status == json.loads(load_fixture("single_peer.json", DOMAIN))


@patch("requests.get", side_effect=requests.RequestException("error"))
def test_get_status_error(mock_get) -> None:
    """Test get_status method with an error."""
    api = WireGuardAPI("error")
    with pytest.raises(WireGuardError):
        api.get_status()


@patch("requests.get", side_effect=mocked_requests)
def test_peers_single_peer(mock_get) -> None:
    """Test get_status method."""
    api = WireGuardAPI("single_peer")
    peers = api.peers

    assert "Dummy" in [peer.name for peer in peers]


def test_peer_from_data() -> None:
    """Test the peer_from_data method."""
    manual_peer1 = WireGuardPeer(
        name="Dummy",
        latest_handshake=None,
        transfer_rx=0,
        transfer_tx=0,
    )
    generated_peer1 = peer_from_data(
        name="Dummy",
        data={
            "latest_handshake": 0,
            "transfer_rx": 0,
            "transfer_tx": 0,
        },
    )

    assert manual_peer1 == generated_peer1

    manual_peer2 = WireGuardPeer(
        name="Dummy",
        latest_handshake=dt.fromtimestamp(float(1)),
        transfer_rx=0,
        transfer_tx=0,
    )
    generated_peer2 = peer_from_data(
        name="Dummy",
        data={
            "latest_handshake": 1,
            "transfer_rx": 0,
            "transfer_tx": 0,
        },
    )

    assert manual_peer2 == generated_peer2
