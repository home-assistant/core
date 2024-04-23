"""Test the duotecno config flow."""

from unittest.mock import AsyncMock, patch

from duotecno.exceptions import InvalidPassword
import pytest

from homeassistant import config_entries
from homeassistant.components.duotecno.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "duotecno.controller.PyDuotecno.connect",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 1234,
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "1.1.1.1"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "port": 1234,
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("test_side_effect", "test_error"),
    [
        (InvalidPassword, "invalid_auth"),
        (ConnectionError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_invalid(hass: HomeAssistant, test_side_effect, test_error):
    """Test all side_effects on the controller.connect via parameters."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("duotecno.controller.PyDuotecno.connect", side_effect=test_side_effect):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 1234,
                "password": "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": test_error}

    with patch("duotecno.controller.PyDuotecno.connect"):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 1234,
                "password": "test-password2",
            },
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "1.1.1.1"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "port": 1234,
        "password": "test-password2",
    }


async def test_already_setup(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test duoteco flow - already setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="duotecno_1234",
        data={},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
