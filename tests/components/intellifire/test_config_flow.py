"""Test the IntelliFire config flow."""
from unittest.mock import Mock, patch

from homeassistant import config_entries
from homeassistant.components.intellifire.config_flow import validate_input
from homeassistant.components.intellifire.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.intellifire.config_flow.validate_input",
        return_value={
            "title": "Living Room Fireplace",
            "type": "Fireplace",
            "serial": "abcd1234",
            "host": "1.1.1.1",
        },
    ), patch(
        "homeassistant.components.intellifire.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        print("mock_setup_entry", mock_setup_entry)
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Fireplace"
    assert result2["data"] == {"host": "1.1.1.1"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "intellifire4py.IntellifireAsync.poll",
        side_effect=ConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_good(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "intellifire4py.IntellifireAsync.poll",
        side_effect=ConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_validate_input(hass: HomeAssistant) -> None:
    """Test for the ideal case."""
    # Define a mock object
    data_mock = Mock()
    data_mock.serial = "12345"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.intellifire.config_flow.validate_input",
        return_value="abcd1234",
    ), patch("intellifire4py.IntellifireAsync.poll", return_value=3), patch(
        "intellifire4py.IntellifireAsync.data", return_value="something"
    ), patch(
        "intellifire4py.IntellifireAsync.data.serial", return_value="1234"
    ), patch(
        "intellifire4py.intellifire_async.IntellifireAsync", return_value="1111"
    ), patch(
        "intellifire4py.IntellifireAsync", return_value=True
    ), patch(
        "intellifire4py.model.IntellifirePollData", new=data_mock
    ) as mobj:
        assert mobj.serial == "12345"

        result = await validate_input(hass, {"host": "127.0.0.1"})

        assert result() == "1234"
