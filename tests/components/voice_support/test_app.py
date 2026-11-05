"""Test reading the app's announcement from the Supervisor."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from aiohasupervisor import SupervisorError
from aiohasupervisor.models import Discovery

from homeassistant.components.voice_support.app import (
    async_get_discovery,
    async_wait_for_discovery,
)
from homeassistant.components.voice_support.const import APP_SLUG
from homeassistant.core import HomeAssistant

UUID_HEX = "0123456789abcdef0123456789abcdef"


def _discovery(addon: str) -> Discovery:
    return Discovery(
        addon=addon,
        service="voice_support",
        uuid=UUID(UUID_HEX),
        config={"host": "f1b2c3d4-voice", "port": 10800},
    )


def _supervisor(messages: list[Discovery] | Exception) -> MagicMock:
    client = MagicMock()
    if isinstance(messages, Exception):
        client.discovery.list = AsyncMock(side_effect=messages)
    else:
        client.discovery.list = AsyncMock(return_value=messages)
    return client


async def test_the_app_among_other_announcements(hass: HomeAssistant) -> None:
    """Test the app's own message is the one that is read."""
    client = _supervisor([_discovery("core_mosquitto"), _discovery(APP_SLUG)])

    with patch(
        "homeassistant.components.voice_support.app.get_supervisor_client",
        return_value=client,
    ):
        app = await async_get_discovery(hass)

    assert app is not None
    assert app.uuid == UUID_HEX
    assert (app.host, app.port) == ("f1b2c3d4-voice", 10800)


async def test_no_announcement_from_the_app(hass: HomeAssistant) -> None:
    """Test another app's message is not mistaken for this one."""
    client = _supervisor([_discovery("core_mosquitto")])

    with patch(
        "homeassistant.components.voice_support.app.get_supervisor_client",
        return_value=client,
    ):
        assert await async_get_discovery(hass) is None


async def test_a_supervisor_that_will_not_answer(hass: HomeAssistant) -> None:
    """Test a Supervisor error is not an exception out of here."""
    client = _supervisor(SupervisorError("no"))

    with patch(
        "homeassistant.components.voice_support.app.get_supervisor_client",
        return_value=client,
    ):
        assert await async_get_discovery(hass) is None


async def test_waiting_for_an_app_that_is_still_starting(
    hass: HomeAssistant,
) -> None:
    """Test the wait ends as soon as the app announces itself."""
    app = object()
    answers = [None, None, app]

    with patch(
        "homeassistant.components.voice_support.app.async_get_discovery",
        AsyncMock(side_effect=answers),
    ):
        assert await async_wait_for_discovery(hass) is app


async def test_waiting_for_an_app_that_never_arrives(hass: HomeAssistant) -> None:
    """Test the wait gives up rather than holding the flow open."""
    with (
        patch("homeassistant.components.voice_support.app.DISCOVERY_TIMEOUT", 0.1),
        patch(
            "homeassistant.components.voice_support.app.async_get_discovery",
            AsyncMock(return_value=None),
        ),
    ):
        assert await async_wait_for_discovery(hass) is None
