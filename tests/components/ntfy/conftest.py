"""Common fixtures for the ntfy tests."""

import asyncio
from collections.abc import AsyncGenerator, Callable, Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from aiontfy import Account, AccountTokenResponse, Event, Notification
import pytest

from homeassistant.components import camera
from homeassistant.components.ntfy.const import CONF_TOPIC, DOMAIN
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ntfy.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_aiontfy() -> Generator[AsyncMock]:
    """Mock aiontfy."""

    with (
        patch("homeassistant.components.ntfy.Ntfy", autospec=True) as mock_client,
        patch("homeassistant.components.ntfy.config_flow.Ntfy", new=mock_client),
    ):
        client = mock_client.return_value

        client.publish.return_value = {}
        client.account.return_value = Account.from_json(
            load_fixture("account.json", DOMAIN)
        )
        client.generate_token.return_value = AccountTokenResponse(
            token="token", last_access=datetime.now()
        )

        resp = Mock(
            id="h6Y2hKA5sy0U",
            time=datetime(2025, 3, 28, 17, 58, 46, tzinfo=UTC),
            expires=datetime(2025, 3, 29, 5, 58, 46, tzinfo=UTC),
            event=Event.MESSAGE,
            topic="mytopic",
            message="Hello",
            title="Title",
            tags=["octopus"],
            priority=3,
            click="https://example.com/",
            icon="https://example.com/icon.png",
            actions=[],
            attachment=None,
            content_type=None,
        )

        resp.to_dict.return_value = {
            "id": "h6Y2hKA5sy0U",
            "time": datetime(2025, 3, 28, 17, 58, 46, tzinfo=UTC),
            "expires": datetime(2025, 3, 29, 5, 58, 46, tzinfo=UTC),
            "event": Event.MESSAGE,
            "topic": "mytopic",
            "message": "Hello",
            "title": "Title",
            "tags": ["octopus"],
            "priority": 3,
            "click": "https://example.com/",
            "icon": "https://example.com/icon.png",
            "actions": [],
            "attachment": None,
            "content_type": None,
        }

        async def mock_ws(
            topics: list[str], callback: Callable[[Notification], None], **kwargs
        ):
            callback(resp)
            while True:
                await asyncio.sleep(1)

        client.subscribe.side_effect = mock_ws

        yield client


@pytest.fixture(autouse=True)
def mock_random() -> Generator[MagicMock]:
    """Mock random."""

    with patch(
        "homeassistant.components.ntfy.config_flow.random.choices",
        return_value=["randomtopic"],
    ) as mock_client:
        yield mock_client


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock ntfy configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="ntfy.sh",
        data={
            CONF_URL: "https://ntfy.sh/",
            CONF_USERNAME: None,
            CONF_TOKEN: "token",
            CONF_VERIFY_SSL: True,
        },
        entry_id="123456789",
        subentries_data=[
            ConfigSubentryData(
                data={CONF_TOPIC: "mytopic"},
                subentry_id="ABCDEF",
                subentry_type="topic",
                title="mytopic",
                unique_id="mytopic",
            )
        ],
    )


@pytest.fixture(name="mock_camera")
async def mock_camera_fixture(hass: HomeAssistant) -> AsyncGenerator[None]:
    """Initialize a demo camera platform."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(
        hass, "camera", {camera.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.demo.camera.Path.read_bytes",
        return_value=b"I play the sax\n",
    ):
        yield


@pytest.fixture(name="mock_image")
async def mock_image_fixture(hass: HomeAssistant) -> AsyncGenerator[None]:
    """Initialize image platform."""
    assert await async_setup_component(hass, "image", {})
    await hass.async_block_till_done()

    image_entity = AsyncMock()
    image_entity.async_image.return_value = b"\x89PNG"

    with (
        patch(
            "homeassistant.helpers.entity_component.EntityComponent.get_entity",
            return_value=image_entity,
        ),
    ):
        yield
