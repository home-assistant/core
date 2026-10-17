"""Common fixtures for the Plexilent tests."""

from collections.abc import Generator
from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock, patch

from pyplexilent import Device
import pytest

from homeassistant.components.plexilent.const import CONF_REFRESH_TOKEN, DOMAIN

from tests.common import MockConfigEntry

DEVICES = [
    Device(
        id="m:2",
        name="Kitchen",
        type="5ch",
        home="m",
        online=True,
        room="Kitchen",
        on=True,
        brightness=40,
        cct=None,
        cct_min=2700,
        cct_max=6500,
        hs=(120, 100),
    ),
    Device(
        id="m:4",
        name="Hall",
        type="dim",
        home="m",
        online=True,
        on=False,
        brightness=100,
    ),
    Device(id="m:5", name="Porch", type="onoff", home="m", online=False, on=False),
    Device(id="m:6", name="Gate", type="onoff", home="m", online=True, on=True),
    Device(id="m:20", name="Switch 20", type="switch", home="m", online=True, on=True),
    Device(
        id="m:22",
        name="Fan",
        type="fan",
        home="m",
        online=True,
        on=True,
        speed=2,
        speeds=4,
    ),
    Device(
        id="m:12", name="Curtain", type="curtain", home="m", online=True, position=40
    ),
    Device(id="m:9", name="Door", type="door", home="m", online=True),
]


@pytest.fixture
def client() -> Generator[MagicMock]:
    """Mock the Plexilent cloud client."""
    c = MagicMock()
    c.login = AsyncMock(return_value="r1")
    c.devices = AsyncMock(return_value=list(DEVICES))
    by_id = {d.id: d for d in DEVICES}
    c.command = AsyncMock(
        side_effect=lambda i, **kw: replace(
            by_id[i], **{k: v for k, v in kw.items() if k != "stop"}
        )
    )
    c.unlink = AsyncMock()
    with (
        patch("homeassistant.components.plexilent.Plexilent", return_value=c),
        patch(
            "homeassistant.components.plexilent.config_flow.Plexilent", return_value=c
        ),
    ):
        yield c


@pytest.fixture
def entry() -> MockConfigEntry:
    """A config entry for one Plexilent account."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="me@x.com",
        title="me@x.com",
        data={"email": "me@x.com", CONF_REFRESH_TOKEN: "r1"},
    )
