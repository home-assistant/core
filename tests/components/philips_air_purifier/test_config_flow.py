"""Test the Philips Air Purifier config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.philips_air_purifier.config_flow import CannotConnect
from homeassistant.components.philips_air_purifier.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.philips_air_purifier.config_flow.PersistentClient.test_connection",
        return_value={
            "name": "Air Purifier",
            "device_id": "fake-device-id",
            "model": "AC2889/10",
        },
    ), patch(
        "homeassistant.components.philips_air_purifier.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Air Purifier"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "model": "AC2889/10",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "exception,expected_err",
    [(CannotConnect, "cannot_connect"), (RuntimeError("unknown"), "unknown")],
)
async def test_form_test_connection_error(
    hass: HomeAssistant, exception, expected_err
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.philips_air_purifier.config_flow.PersistentClient.test_connection",
        side_effect=exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": expected_err}
