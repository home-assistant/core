"""VeSync component tests."""
import pytest
from unittest.mock import MagicMock, patch
from homeassistant import config_entries, data_entry_flow
from homeassistant.components import vesync
from homeassistant.components.vesync.common import (
    CONF_LIGHTS,
    CONF_SWITCHES,
    CONF_FANS
)
from homeassistant.setup import async_setup_component
from tests.common import MockDependency, MockConfigEntry, mock_coro

from pyvesync.vesync import VeSync

MOCK_VS = MockDependency("pyvesync")


async def test_create_entry(hass):
    """Test creating user/pass entry."""
    with MOCK_VS, patch("pyvesync.vesync.VeSync") as vs_obj, patch(
            "homeassistant.components.vesync.async_setup_entry",
            return_value=mock_coro(True)) as mock_setup, patch(
                "pyvesync.vesync.VeSync", return_value=vs_obj):
        result = await hass.config_entries.flow.async_init(
            vesync.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1
