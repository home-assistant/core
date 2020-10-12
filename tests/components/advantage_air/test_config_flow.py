"""Test the Advantage Air config flow."""

from advantage_air import ApiError

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.advantage_air.const import DOMAIN

from tests.async_mock import patch
from tests.components.advantage_air import TEST_SYSTEM_DATA, TEST_SYSTEM_URL, USER_INPUT


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
        TEST_SYSTEM_URL,
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
        TEST_SYSTEM_URL,
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
