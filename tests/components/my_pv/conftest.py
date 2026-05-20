"""Common fixtures for the my-PV tests."""

import pytest

from homeassistant.components.my_pv.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD

from tests.common import MockConfigEntry


@pytest.fixture
def mock_local_config_entry() -> MockConfigEntry:
    """Return the my-PV mocked config entry for local devices."""
    return MockConfigEntry(
        title="my-PV AC ELWA 2",
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PASSWORD: "test-password",
        },
        unique_id="1601500000000000",
    )
