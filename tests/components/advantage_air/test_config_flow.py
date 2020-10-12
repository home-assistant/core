"""Test the Advantage Air config flow."""

from advantage_air import ApiError

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.advantage_air.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT

from tests.async_mock import patch
from tests.common import load_fixture

TEST_SYSTEM_DATA = load_fixture("advantage_air/getSystemData.json")

USER_INPUT = {
    CONF_IP_ADDRESS: "1.2.3.4",
    CONF_PORT: 2025,
}


async def test_form(hass, aioclient_mock):
    """Test that form shows up."""
    with patch(
        "homeassistant.components.advantage_air.async_setup", return_value=True
    ) as mock_setup:
        await setup.async_setup_component(hass, DOMAIN, {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    aioclient_mock.get(
        f"http://{USER_INPUT[CONF_IP_ADDRESS]}:{USER_INPUT[CONF_PORT]}/getSystemData",
        text=TEST_SYSTEM_DATA,
    )

    with patch(
        "homeassistant.components.advantage_air.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert len(aioclient_mock.mock_calls) == 1
    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "testname"
    assert result2["data"] == USER_INPUT
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass, aioclient_mock):
    """Test we handle cannot connect error."""

    aioclient_mock.get(
        f"http://{USER_INPUT[CONF_IP_ADDRESS]}:{USER_INPUT[CONF_PORT]}/getSystemData",
        exc=ApiError("TestError"),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}
    assert len(aioclient_mock.mock_calls) == 1
