"""Tests for Glances config flow."""
from glances_api.exceptions import GlancesApiConnectionError

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import glances
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from . import MOCK_CONFIG_DATA

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def glances_setup_fixture():
    """Mock transmission entry setup."""
    with patch("homeassistant.components.glances.async_setup_entry", return_value=True):
        yield


async def test_form(hass: HomeAssistant) -> None:
    """Test config entry configured successfully."""

    result = await hass.config_entries.flow.async_init(
        glances.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG_DATA
    )

    assert result["type"] == "create_entry"
    assert result["title"] == HOST
    assert result["data"] == DEMO_USER_INPUT


async def test_form_cannot_connect(hass: HomeAssistant, mock_api):
    """Test to return error if we cannot connect."""

    mock_api.return_value.get_data.side_effect = GlancesApiConnectionError
    result = await hass.config_entries.flow.async_init(
        glances.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG_DATA
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test host is already configured."""
    entry = MockConfigEntry(
        domain=glances.DOMAIN, data=MOCK_CONFIG_DATA, options={CONF_SCAN_INTERVAL: 60}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        glances.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG_DATA
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
