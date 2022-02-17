"""Common fixtures for sleepiq tests."""
import json
from unittest.mock import patch

import pytest
from sleepyq import Bed, FamilyStatus, Sleeper

from homeassistant.components.sleepiq.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry, load_fixture


def mock_beds(account_type):
    """Mock sleepnumber bed data."""
    return [
        Bed(bed)
        for bed in json.loads(load_fixture(f"bed{account_type}.json", "sleepiq"))[
            "beds"
        ]
    ]


def mock_sleepers():
    """Mock sleeper data."""
    return [
        Sleeper(sleeper)
        for sleeper in json.loads(load_fixture("sleeper.json", "sleepiq"))["sleepers"]
    ]


def mock_bed_family_status(account_type):
    """Mock family status data."""
    return [
        FamilyStatus(status)
        for status in json.loads(
            load_fixture(f"familystatus{account_type}.json", "sleepiq")
        )["beds"]
    ]


@pytest.fixture
def config_data():
    """Provide configuration data for tests."""
    return {
        CONF_USERNAME: "username",
        CONF_PASSWORD: "password",
    }


@pytest.fixture
def config_entry(config_data):
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=config_data,
        options={},
    )


@pytest.fixture(params=["-single", ""])
async def setup_entry(hass, request, config_entry):
    """Initialize the config entry."""
    with patch("sleepyq.Sleepyq.beds", return_value=mock_beds(request.param)), patch(
        "sleepyq.Sleepyq.sleepers", return_value=mock_sleepers()
    ), patch(
        "sleepyq.Sleepyq.bed_family_status",
        return_value=mock_bed_family_status(request.param),
    ), patch(
        "sleepyq.Sleepyq.login"
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        return {"account_type": request.param, "mock_entry": config_entry}
