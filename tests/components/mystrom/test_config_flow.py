"""Test the myStrom config flow."""
from unittest.mock import AsyncMock, patch

from pymystrom.exceptions import MyStromConnectionError
import pytest

from homeassistant import config_entries
from homeassistant.components.mystrom.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

DEVICE_MAC = "6001940376EB"

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form_combined(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "pymystrom.get_device_info",
        side_effect=AsyncMock(return_value={"type": 101, "mac": DEVICE_MAC}),
    ) as mock_session:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == DEVICE_MAC
        assert result2["data"] == {"host": "1.1.1.1"}

    # test for duplicates
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "pymystrom.get_device_info",
        return_value={"type": 101, "mac": DEVICE_MAC},
    ) as mock_session:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] == FlowResultType.ABORT

    assert len(mock_session.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_duplicates(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "pymystrom.get_device_info",
        return_value={"type": 101, "mac": DEVICE_MAC},
    ) as mock_session:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == DEVICE_MAC
        assert result2["data"] == {"host": "1.1.1.1"}

    assert len(mock_session.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_step_import(hass: HomeAssistant) -> None:
    """Test the import step."""
    conf = {
        CONF_HOST: "1.1.1.1",
    }
    with patch("pymystrom.switch.MyStromSwitch.get_state"), patch(
        "pymystrom.get_device_info",
        return_value={"type": 101, "mac": DEVICE_MAC},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=conf
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == DEVICE_MAC
        assert result["data"] == {
            CONF_HOST: "1.1.1.1",
        }


async def test_wong_answer_from_device(hass: HomeAssistant) -> None:
    """Test the import step."""
    conf = {
        CONF_HOST: "1.1.1.1",
    }
    with patch("pymystrom.switch.MyStromSwitch.get_state"), patch(
        "pymystrom.get_device_info",
        side_effect=MyStromConnectionError(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=conf
        )
        assert result["type"] == FlowResultType.FORM
