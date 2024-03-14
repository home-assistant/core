"""Test mailbox."""

from collections.abc import Generator
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.asterisk_mbox import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .const import CONFIG


@pytest.fixture
def client() -> Generator[Mock, None, None]:
    """Mock client."""
    with patch(
        "homeassistant.components.asterisk_mbox.asteriskClient", autospec=True
    ) as client:
        yield client


async def test_repair_issue_is_created(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    client: Mock,
) -> None:
    """Test repair issue is created."""
    assert await async_setup_component(hass, DOMAIN, CONFIG)
    await hass.async_block_till_done()
    assert (
        DOMAIN,
        "deprecated_integration",
    ) in issue_registry.issues
