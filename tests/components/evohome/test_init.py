"""The tests for evohome."""

from __future__ import annotations

from http import HTTPStatus
import logging
from unittest.mock import patch

from evohomeasync2 import exceptions as exc
from evohomeasync2.broker import _ERR_MSG_LOOKUP_AUTH, _ERR_MSG_LOOKUP_BASE
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.evohome import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import setup_evohome
from .const import TEST_INSTALLS


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_entities(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities and state after setup of a Honeywell TCC-compatible system."""

    # some extended state attrs are relative the current time
    freezer.move_to("2024-07-10 12:00:00+00:00")

    await setup_evohome(hass, config, install=install)

    assert hass.states.async_all() == snapshot


@pytest.mark.parametrize(
    "status", [*sorted([*_ERR_MSG_LOOKUP_AUTH, HTTPStatus.BAD_GATEWAY]), None]
)
async def test_authentication_failure_v2(
    hass: HomeAssistant,
    config: dict[str, str],
    status: HTTPStatus,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test failure to setup an evohome-compatible system."""

    with patch("evohomeasync2.broker.Broker.get") as mock_fcn:
        mock_fcn.side_effect = exc.AuthenticationFailed("", status=status)

        with caplog.at_level(logging.WARNING):
            result = await async_setup_component(hass, DOMAIN, {DOMAIN: config})

    assert result is False

    assert caplog.record_tuples == [
        (
            "homeassistant.components.evohome.helpers",
            logging.ERROR,
            "Failed to authenticate with the vendor's server. Check your username and password. NB: Some special password characters that work correctly via the website will not work via the web API. Message is: ",
        ),
        (
            "homeassistant.setup",
            logging.ERROR,
            "Setup failed for 'evohome': Integration failed to initialize.",
        ),
    ]


@pytest.mark.parametrize(
    "status", [*sorted([*_ERR_MSG_LOOKUP_BASE, HTTPStatus.BAD_GATEWAY]), None]
)
async def test_client_request_failure_v2(
    hass: HomeAssistant,
    config: dict[str, str],
    status: HTTPStatus,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test failure to setup an evohome-compatible system."""

    with patch("evohomeasync2.broker.Broker.get") as mock_fcn:
        mock_fcn.side_effect = exc.RequestFailed("", status=status)

        with caplog.at_level(logging.WARNING):
            result = await async_setup_component(hass, DOMAIN, {DOMAIN: config})

    assert result is False

    # ignore any logging from the client library
    log = [r.message for r in caplog.records if r.name.startswith("homeassistant.")]

    if status in (
        HTTPStatus.TOO_MANY_REQUESTS,
        HTTPStatus.SERVICE_UNAVAILABLE,
        None,
    ):
        assert log[1].startswith("Setup failed for")
        assert len(log) == 2
    else:
        assert log[0].startswith("Error during setup of")
        assert len(log) == 1

    # these entries are from evohome
    if status == HTTPStatus.TOO_MANY_REQUESTS:
        assert "API rate limit" in log[0]
    elif status == HTTPStatus.SERVICE_UNAVAILABLE:
        assert "currently unavailable" in log[0]
    elif status is None:
        assert "Unable to connect" in log[0]
