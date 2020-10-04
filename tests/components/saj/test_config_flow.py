"""Tests for SAJ config flow."""
import pytest

from homeassistant.components.saj.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TYPE

from tests.async_mock import Mock, patch

MOCK_USER_DATA = {
    CONF_HOST: "fake_host",
    CONF_TYPE: "wifi",
}


@pytest.fixture(name="inverter")
def remote_fixture():
    """Patch the SAJInverter."""

    async def mock_connect():
        pass

    with patch("homeassistant.components.saj.sensor.SAJInverter") as inverter_class:
        inverter = Mock()
        inverter.connect = mock_connect
        inverter_class.return_value = inverter
        yield inverter


async def test_user(hass, inverter):
    """Test starting a flow by user."""
    # show form
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    # entry was added
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_USER_DATA
    )
    await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == "fake_host"
    assert result["data"][CONF_HOST] == "fake_host"
    assert result["data"][CONF_TYPE] == "wifi"
    assert result["data"][CONF_NAME] == ""


async def test_user_already_configured(hass, inverter):
    """Test starting a flow by user when already configured."""

    # entry was added
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
    )
    await hass.async_block_till_done()
    assert result["type"] == "create_entry"

    # failed as already configured
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=MOCK_USER_DATA
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
