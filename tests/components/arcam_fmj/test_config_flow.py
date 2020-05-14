"""Tests for the Arcam FMJ config flow module."""

import pytest

from homeassistant import data_entry_flow
from homeassistant.components.arcam_fmj.config_flow import ArcamFmjFlowHandler
from homeassistant.components.arcam_fmj.const import DOMAIN

from .conftest import MOCK_CONFIG, MOCK_NAME

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def config_entry_fixture():
    """Create a mock Arcam config entry."""
    return MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, title=MOCK_NAME)


async def test_single_import_only(hass, config_entry):
    """Test form is shown when host not provided."""
    config_entry.add_to_hass(hass)
    flow = ArcamFmjFlowHandler()
    flow.hass = hass
    result = await flow.async_step_import(MOCK_CONFIG)
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_setup"


async def test_import(hass):
    """Test form is shown when host not provided."""
    flow = ArcamFmjFlowHandler()
    flow.hass = hass
    result = await flow.async_step_import(MOCK_CONFIG)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Arcam FMJ"
    assert result["data"] == MOCK_CONFIG
