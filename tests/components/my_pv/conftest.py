"""Common fixtures for the my-PV tests."""

import pytest

from homeassistant.components.my_pv.const import (
    CONF_SERIAL_NUMBER,
    CONF_TYPE_CLOUD,
    CONF_TYPE_LOCAL,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_TYPE

from tests.common import MockConfigEntry


@pytest.fixture
def mock_local_config_entry() -> MockConfigEntry:
    """Return the my-PV mocked config entry for local devices."""
    return MockConfigEntry(
        title="my-PV AC ELWA 2",
        domain=DOMAIN,
        data={
            CONF_TYPE: CONF_TYPE_LOCAL,
            CONF_HOST: "127.0.0.1",
            CONF_PASSWORD: "test-password",
        },
        unique_id="1601500000000000",
    )


@pytest.fixture
def mock_cloud_config_entry() -> MockConfigEntry:
    """Return the my-PV mocked config entry for cloud devices."""
    return MockConfigEntry(
        title="my-PV AC ELWA 2",
        domain=DOMAIN,
        data={
            CONF_TYPE: CONF_TYPE_CLOUD,
            CONF_SERIAL_NUMBER: "1601500000000000",
            CONF_TOKEN: "my0000000000000000000000000000000000000000000000PV",
        },
        unique_id="1601500000000000",
    )
