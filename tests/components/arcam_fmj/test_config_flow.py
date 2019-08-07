"""Tests for the Arcam FMJ config flow module."""
import pytest
from homeassistant import data_entry_flow
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry, MockDependency

with MockDependency("arcam"), MockDependency("arcam.fmj"), MockDependency(
    "arcam.fmj.client"
):
    from homeassistant.components.arcam_fmj import DEVICE_SCHEMA
    from homeassistant.components.arcam_fmj.config_flow import ArcamFmjFlowHandler
    from homeassistant.components.arcam_fmj.const import DOMAIN

    MOCK_HOST = "127.0.0.1"
    MOCK_PORT = 1234
    MOCK_NAME = "Arcam FMJ"
    MOCK_CONFIG = DEVICE_SCHEMA({CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT})

    @pytest.fixture(name="config_entry")
    def config_entry_fixture():
        """Create a mock HEOS config entry."""
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
        assert result["title"] == MOCK_NAME
        assert result["data"] == MOCK_CONFIG
