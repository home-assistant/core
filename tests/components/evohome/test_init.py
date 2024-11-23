"""The tests for evohome."""

from __future__ import annotations

from http import HTTPStatus
import logging
from unittest.mock import patch

from evohomeasync2 import EvohomeClient, exceptions as exc
from evohomeasync2.broker import _ERR_MSG_LOOKUP_AUTH, _ERR_MSG_LOOKUP_BASE
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.evohome import DOMAIN, EvoService
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import TEST_INSTALLS

SETUP_FAILED_ANTICIPATED = (
    "homeassistant.setup",
    logging.ERROR,
    "Setup failed for 'evohome': Integration failed to initialize.",
)
SETUP_FAILED_UNEXPECTED = (
    "homeassistant.setup",
    logging.ERROR,
    "Error during setup of component evohome",
)
AUTHENTICATION_FAILED = (
    "homeassistant.components.evohome.helpers",
    logging.ERROR,
    "Failed to authenticate with the vendor's server. Check your username"
    " and password. NB: Some special password characters that work"
    " correctly via the website will not work via the web API. Message"
    " is: ",
)
REQUEST_FAILED_NONE = (
    "homeassistant.components.evohome.helpers",
    logging.WARNING,
    "Unable to connect with the vendor's server. "
    "Check your network and the vendor's service status page. "
    "Message is: ",
)
REQUEST_FAILED_503 = (
    "homeassistant.components.evohome.helpers",
    logging.WARNING,
    "The vendor says their server is currently unavailable. "
    "Check the vendor's service status page",
)
REQUEST_FAILED_429 = (
    "homeassistant.components.evohome.helpers",
    logging.WARNING,
    "The vendor's API rate limit has been exceeded. "
    "If this message persists, consider increasing the scan_interval",
)

REQUEST_FAILED_LOOKUP = {
    None: [
        REQUEST_FAILED_NONE,
        SETUP_FAILED_ANTICIPATED,
    ],
    HTTPStatus.SERVICE_UNAVAILABLE: [
        REQUEST_FAILED_503,
        SETUP_FAILED_ANTICIPATED,
    ],
    HTTPStatus.TOO_MANY_REQUESTS: [
        REQUEST_FAILED_429,
        SETUP_FAILED_ANTICIPATED,
    ],
}


@pytest.mark.parametrize(
    "status", [*sorted([*_ERR_MSG_LOOKUP_AUTH, HTTPStatus.BAD_GATEWAY]), None]
)
async def test_authentication_failure_v2(
    hass: HomeAssistant,
    config: dict[str, str],
    status: HTTPStatus,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test failure to setup an evohome-compatible system.

    In this instance, the failure occurs in the v2 API.
    """

    with patch("evohomeasync2.broker.Broker.get") as mock_fcn:
        mock_fcn.side_effect = exc.AuthenticationFailed("", status=status)

        with caplog.at_level(logging.WARNING):
            result = await async_setup_component(hass, DOMAIN, {DOMAIN: config})

    assert result is False

    assert caplog.record_tuples == [
        AUTHENTICATION_FAILED,
        SETUP_FAILED_ANTICIPATED,
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
    """Test failure to setup an evohome-compatible system.

    In this instance, the failure occurs in the v2 API.
    """

    with patch("evohomeasync2.broker.Broker.get") as mock_fcn:
        mock_fcn.side_effect = exc.RequestFailed("", status=status)

        with caplog.at_level(logging.WARNING):
            result = await async_setup_component(hass, DOMAIN, {DOMAIN: config})

    assert result is False

    assert caplog.record_tuples == REQUEST_FAILED_LOOKUP.get(
        status, [SETUP_FAILED_UNEXPECTED]
    )


@pytest.mark.parametrize("install", [*TEST_INSTALLS, "botched"])
async def test_setup(
    hass: HomeAssistant,
    evohome: EvohomeClient,
    snapshot: SnapshotAssertion,
) -> None:
    """Test services after setup of evohome.

    Registered services vary by the type of system.
    """

    assert hass.services.async_services_for_domain(DOMAIN).keys() == snapshot


@pytest.mark.parametrize("install", ["default"])
async def test_service_refresh_system(
    hass: HomeAssistant,
    evohome: EvohomeClient,
) -> None:
    """Test EvoService.REFRESH_SYSTEM of an evohome system."""

    # EvoService.REFRESH_SYSTEM
    with patch("evohomeasync2.location.Location.refresh_status") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.REFRESH_SYSTEM,
            {},
            blocking=True,
        )

        assert mock_fcn.await_count == 1
        assert mock_fcn.await_args.args == ()
        assert mock_fcn.await_args.kwargs == {}


@pytest.mark.parametrize("install", ["default"])
async def test_service_reset_system(
    hass: HomeAssistant,
    evohome: EvohomeClient,
) -> None:
    """Test EvoService.RESET_SYSTEM of an evohome system."""

    # EvoService.RESET_SYSTEM (if SZ_AUTO_WITH_RESET in modes)
    with patch("evohomeasync2.controlsystem.ControlSystem.set_mode") as mock_fcn:
        await hass.services.async_call(
            DOMAIN,
            EvoService.RESET_SYSTEM,
            {},
            blocking=True,
        )

        assert mock_fcn.await_count == 1
        assert mock_fcn.await_args.args == ("AutoWithReset",)
        assert mock_fcn.await_args.kwargs == {"until": None}
