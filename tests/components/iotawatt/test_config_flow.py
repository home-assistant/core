"""Test the IoTawatt config flow."""

from unittest.mock import patch

import httpx

from homeassistant import config_entries
from homeassistant.components.iotawatt.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def _async_connect_with_mac(iotawatt):
    """Mock IoTaWatt connection that sets a MAC address."""
    iotawatt._macAddress = "mock-mac"
    return True


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    with (
        patch(
            "homeassistant.components.iotawatt.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.iotawatt.config_flow.Iotawatt.connect",
            new=_async_connect_with_mac,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        "host": "1.1.1.1",
    }
    assert result2["result"].unique_id == "mock-mac"


async def test_form_auth(hass: HomeAssistant) -> None:
    """Test we handle auth."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.iotawatt.config_flow.Iotawatt.connect",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "auth"

    with patch(
        "homeassistant.components.iotawatt.config_flow.Iotawatt.connect",
        return_value=False,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "mock-user",
                "password": "mock-pass",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "auth"
    assert result3["errors"] == {"base": "invalid_auth"}

    with (
        patch(
            "homeassistant.components.iotawatt.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.iotawatt.config_flow.Iotawatt.connect",
            new=_async_connect_with_mac,
        ),
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "mock-user",
                "password": "mock-pass",
            },
        )
        await hass.async_block_till_done()

    assert result4["type"] is FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1
    assert result4["data"] == {
        "host": "1.1.1.1",
        "username": "mock-user",
        "password": "mock-pass",
    }
    assert result4["result"].unique_id == "mock-mac"


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.iotawatt.config_flow.Iotawatt.connect",
        side_effect=httpx.HTTPError("any"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_setup_exception(hass: HomeAssistant) -> None:
    """Test we handle broad exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.iotawatt.config_flow.Iotawatt.connect",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "1.1.1.1"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_updates_existing_entry(hass: HomeAssistant) -> None:
    """Test rediscovery updates host on an existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1"},
        unique_id="mock-mac",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.iotawatt.config_flow.Iotawatt.connect",
            new=_async_connect_with_mac,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "2.2.2.2",
            },
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "2.2.2.2"
