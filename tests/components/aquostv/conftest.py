"""Fixtures for the Sharp Aquos TV tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.aquostv.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME

HOST = "192.168.1.50"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Sharp Aquos TV",
        data={
            CONF_HOST: HOST,
            CONF_PORT: 10002,
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
    )


@pytest.fixture
def mock_tv() -> Generator[MagicMock]:
    """Mock the Sharp Aquos library."""
    with patch("sharp_aquos_rc.TV", autospec=True) as tv_class:
        tv = tv_class.return_value
        tv.info.return_value = {"name": "TV", "model": "LC-40", "version": "1"}
        tv.power.return_value = 1
        tv.mute.return_value = 2
        tv.input.return_value = 1
        tv.volume.return_value = 30
        yield tv
