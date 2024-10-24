"""Tests for AIS tracker config flow."""

from unittest.mock import patch

from homeassistant.components.ais_tracker.const import CONF_MMSIS, DOMAIN
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import MOCK_USER_DATA

from tests.common import MockConfigEntry

MOCK_USER_DATA2 = {CONF_PORT: 23456, CONF_MMSIS: ["123456789"]}


async def test_user(hass: HomeAssistant) -> None:
    """Test starting a flow by user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.ais_tracker.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == MOCK_USER_DATA
        assert result["title"] == "AIS listener on 12346"

        await hass.async_block_till_done()

    assert mock_setup_entry.called


async def test_user_already_configured(hass: HomeAssistant) -> None:
    """Test starting a flow by user with an already configured statioon."""
    mock_config = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    mock_config.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_USER_DATA
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_successful(hass: HomeAssistant) -> None:
    """Test starting a reconfigure flow."""
    mock_config = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.ais_tracker.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        await hass.config_entries.async_setup(mock_config.entry_id)

    assert mock_setup_entry.called

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_RECONFIGURE,
            "entry_id": mock_config.entry_id,
        },
        data=mock_config.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_confirm"

    with patch(
        "homeassistant.components.ais_tracker.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_USER_DATA2,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config.data == MOCK_USER_DATA2
