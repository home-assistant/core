"""Tests covering HA+tradfri+pytradfri (mock aiocoap external lib)."""
import logging
from unittest.mock import patch

import pytest

from homeassistant.components.tradfri import DOMAIN

from . import MOCK_GATEWAY_ID

from tests.common import MockConfigEntry

# ----- Parts used  from aiocoap library -----
# Mocked --> Context, Message
""""
from aiocoap.credentials import CredentialsMissingError
from aiocoap.error import (
    ConstructionRenderableError,
    Error,
    LibraryShutdown,
    RequestTimedOut,
)
from aiocoap.numbers.codes import Code
"""

_LOGGER = logging.getLogger(__name__)


# ----- Fixtures  -----
# pytradfri does ->> from aiocoap import Context
@pytest.fixture
def Context():
    """Mock aiocoap Context."""
    with patch("pytradfri.api.aiocoap_api.Context", autospec=True) as api:
        yield api


# pytradfri does ->> from aiocoap import Message
@pytest.fixture
def Message():
    """Mock aiocoap Message."""
    with patch("pytradfri.api.aiocoap_api.Message", autospec=True) as api:
        yield api


# start tradfri
@pytest.fixture
async def start_tradfri(hass):
    """Start tradfri (run setup)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "mock-host",
            "identity": "mock-identity",
            "key": "mock-key",
            "import_groups": True,
            "gateway_id": MOCK_GATEWAY_ID,
        },
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_simulator(Context, Message, start_tradfri):
    """Simulate aiocoap library."""
    return


# Context -->>>
# self._protocol = asyncio.create_task(Context.create_client_context())


# Message -->>>
# msg = Message(code=api_method, uri=url, **kwargs)
# msg = Message(code=Code.GET, uri=url, observe=duration)
# --
# pr = protocol.request(msg)
# msg = Message(code=api_method, uri=url, **kwargs)
# _, res = await self._get_response(msg)
# msg = Message(code=Code.GET, uri=url, observe=duration)
# pr, r = await self._get_response(msg)
