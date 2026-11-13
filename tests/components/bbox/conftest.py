"""Fixtures for the bbox tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.bbox.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_VERIFY_SSL

from .const import DEVICE, HOST, HOSTS, PASSWORD, STATS


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a bbox config entry with a password."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DEVICE.serialnumber,
        title=HOST,
        data={
            CONF_HOST: HOST,
            CONF_PASSWORD: PASSWORD,
            CONF_VERIFY_SSL: True,
        },
    )


@pytest.fixture
def mock_bbox_client() -> Generator[MagicMock]:
    """Patch the BboxClient used by the integration and by the config flow."""
    with (
        patch("homeassistant.components.bbox.BboxClient") as client_class,
        patch("homeassistant.components.bbox.config_flow.BboxClient", client_class),
    ):
        client = client_class.return_value
        client.get_device = AsyncMock(return_value=DEVICE)
        client.get_wan_ip_stats = AsyncMock(return_value=STATS)
        client.get_hosts = AsyncMock(return_value=list(HOSTS))
        client.close = AsyncMock()
        yield client_class
