"""Test configuration for the Vultr tests."""

import pytest

from homeassistant.core import HomeAssistant

from tests.common import load_fixture


@pytest.fixture(name="valid_config")
def valid_config(hass: HomeAssistant, requests_mock):
    """Load a valid config."""
    requests_mock.get(
        "https://api.vultr.com/v2/instances/db731ada-1326-4186-85dc-c88b899c6639",
        text=load_fixture(
            "instance_db731ada-1326-4186-85dc-c88b899c6639.json", "vultr"
        ),
    )
    requests_mock.get(
        "https://api.vultr.com/v2/instances/db731ada-1326-4186-85dc-c88b899c6640",
        text=load_fixture(
            "instance_db731ada-1326-4186-85dc-c88b899c6640.json", "vultr"
        ),
    )

    requests_mock.get(
        "https://api.vultr.com/v2/instances/db731ada-1326-4186-85dc-c88b899c6641",
        text=load_fixture(
            "instance_db731ada-1326-4186-85dc-c88b899c6641.json", "vultr"
        ),
    )

    requests_mock.get(
        "https://api.vultr.com/v2/account",
        text=load_fixture("account_info.json", "vultr"),
    )
    requests_mock.get(
        "https://api.vultr.com/v2/account/bandwidth",
        text=load_fixture("account_bandwidth.json", "vultr"),
    )
