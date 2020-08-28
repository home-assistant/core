"""Test the Plugwise config flow."""
from Plugwise_Smile.Smile import Smile
import pytest

from homeassistant import config_entries, setup
from homeassistant.components.plugwise.const import DOMAIN

from tests.async_mock import patch


@pytest.fixture(name="mock_smile")
def mock_smile():
    """Create a Mock Smile for testing exceptions."""
    with patch(
        "homeassistant.components.plugwise.config_flow.Smile",
    ) as smile_mock:
        smile_mock.PlugwiseError = Smile.PlugwiseError
        smile_mock.InvalidAuthentication = Smile.InvalidAuthentication
        smile_mock.ConnectionFailedError = Smile.ConnectionFailedError
        smile_mock.return_value.connect.return_value = True
        yield smile_mock.return_value


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.plugwise.config_flow.Smile.connect",
        return_value=True,
    ), patch(
        "homeassistant.components.plugwise.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.plugwise.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1", "password": "test-password"},
        )

    assert result2["type"] == "create_entry"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "password": "test-password",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass, mock_smile):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_smile.connect.side_effect = Smile.InvalidAuthentication
    mock_smile.gateway_id = "0a636a4fc1704ab4a24e4f7e37fb187a"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "1.1.1.1", "password": "test-password"},
    )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass, mock_smile):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_smile.connect.side_effect = Smile.ConnectionFailedError
    mock_smile.gateway_id = "0a636a4fc1704ab4a24e4f7e37fb187a"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "1.1.1.1", "password": "test-password"},
    )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
