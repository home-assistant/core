"""Provide common pytest fixtures."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant

from .const import TOKEN


@pytest.fixture(name="client")
def client_fixture() -> Generator[MagicMock]:
    """Create a mock client."""
    client = MagicMock()
    with (
        patch(
            "homeassistant.components.remember_the_milk.entity.Rtm"
        ) as entity_client_class,
        patch("homeassistant.components.remember_the_milk.Rtm") as client_class,
    ):
        entity_client_class.return_value = client
        client_class.return_value = client
        client.token = TOKEN
        client.token_valid.return_value = True
        timelines = MagicMock()
        timelines.timeline.value = "1234"
        client.rtm.timelines.create.return_value = timelines
        add_response = MagicMock()
        add_response.list.id = "1"
        add_response.list.taskseries.id = "2"
        add_response.list.taskseries.task.id = "3"
        client.rtm.tasks.add.return_value = add_response

        yield client


@pytest.fixture
async def storage(hass: HomeAssistant, client) -> AsyncGenerator[MagicMock]:
    """Mock the config storage."""
    with patch(
        "homeassistant.components.remember_the_milk.RememberTheMilkConfiguration"
    ) as storage_class:
        storage = storage_class.return_value
        storage.get_token.return_value = TOKEN
        storage.get_rtm_id.return_value = None
        yield storage
