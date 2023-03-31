"""Test the moehlenhoff_alpha2 config flow."""
import asyncio
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.moehlenhoff_alpha2.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_BASE_ID = "fake-base-id"
MOCK_BASE_NAME = "fake-base-name"
MOCK_BASE_HOST = "fake-base-host"


async def mock_update_data(self):
    """Mock moehlenhoff_alpha2.Alpha2Base.update_data."""
    self.static_data = {
        "Devices": {
            "Device": {"ID": MOCK_BASE_ID, "NAME": MOCK_BASE_NAME, "HEATAREA": []}
        }
    }


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == FlowResultType.FORM
    assert not result["errors"]

    with patch("moehlenhoff_alpha2.Alpha2Base.update_data", mock_update_data), patch(
        "homeassistant.components.moehlenhoff_alpha2.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"],
            user_input={"host": MOCK_BASE_HOST},
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == MOCK_BASE_NAME
    assert result2["data"] == {"host": MOCK_BASE_HOST}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_duplicate_error(hass: HomeAssistant) -> None:
    """Test that errors are shown when duplicates are added."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": MOCK_BASE_HOST},
        source=config_entries.SOURCE_USER,
    )
    config_entry.add_to_hass(hass)

    assert config_entry.data["host"] == MOCK_BASE_HOST

    with patch("moehlenhoff_alpha2.Alpha2Base.update_data", mock_update_data):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            data={"host": MOCK_BASE_HOST},
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_form_cannot_connect_error(hass: HomeAssistant) -> None:
    """Test connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "moehlenhoff_alpha2.Alpha2Base.update_data", side_effect=asyncio.TimeoutError
    ):
        result2 = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"],
            user_input={"host": MOCK_BASE_HOST},
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unexpected_error(hass: HomeAssistant) -> None:
    """Test unexpected error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch("moehlenhoff_alpha2.Alpha2Base.update_data", side_effect=Exception):
        result2 = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"],
            user_input={"host": MOCK_BASE_HOST},
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"] == {"base": "unknown"}
