"""Test the Adax config flow."""
from unittest.mock import patch

import adax_local

from homeassistant import config_entries
from homeassistant.components.adax.const import (
    ACCOUNT_ID,
    CLOUD,
    CONNECTION_TYPE,
    DOMAIN,
    LOCAL,
    WIFI_PSWD,
    WIFI_SSID,
)
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_DATA = {
    ACCOUNT_ID: 12345,
    CONF_PASSWORD: "pswd",
}


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: CLOUD,
        },
    )
    assert result2["type"] == FlowResultType.FORM

    with patch(
        "adax.get_adax_token",
        return_value="test_token",
    ), patch(
        "homeassistant.components.adax.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            TEST_DATA,
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == str(TEST_DATA["account_id"])
    assert result3["data"] == {
        ACCOUNT_ID: TEST_DATA["account_id"],
        CONF_PASSWORD: TEST_DATA["password"],
        CONNECTION_TYPE: CLOUD,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: CLOUD,
        },
    )
    assert result2["type"] == FlowResultType.FORM

    with patch(
        "adax.get_adax_token",
        return_value=None,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            TEST_DATA,
        )
    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "cannot_connect"}


async def test_flow_entry_already_exists(hass: HomeAssistant) -> None:
    """Test user input for config_entry that already exists."""

    first_entry = MockConfigEntry(
        domain="adax",
        data=TEST_DATA,
        unique_id=str(TEST_DATA[ACCOUNT_ID]),
    )
    first_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: CLOUD,
        },
    )
    assert result2["type"] == FlowResultType.FORM

    with patch("adax.get_adax_token", return_value="token"):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            TEST_DATA,
        )
        await hass.async_block_till_done()

    assert result3["type"] == "abort"
    assert result3["reason"] == "already_configured"


# local API:


async def test_local_create_entry(hass: HomeAssistant) -> None:
    """Test create entry from user input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: LOCAL,
        },
    )
    assert result2["type"] == FlowResultType.FORM

    test_data = {
        WIFI_SSID: "ssid",
        WIFI_PSWD: "pswd",
    }

    with patch(
        "homeassistant.components.adax.async_setup_entry",
        return_value=True,
    ), patch(
        "homeassistant.components.adax.config_flow.adax_local.AdaxConfig", autospec=True
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.configure_device.return_value = True
        client.device_ip = "192.168.1.4"
        client.access_token = "token"
        client.mac_id = "8383838"
        result = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            test_data,
        )

    test_data[CONNECTION_TYPE] = LOCAL
    assert result["type"] == "create_entry"
    assert result["title"] == "8383838"
    assert result["data"] == {
        "connection_type": "Local",
        "ip_address": "192.168.1.4",
        "token": "token",
        "unique_id": "8383838",
    }


async def test_local_flow_entry_already_exists(hass: HomeAssistant) -> None:
    """Test user input for config_entry that already exists."""

    test_data = {
        WIFI_SSID: "ssid",
        WIFI_PSWD: "pswd",
    }

    first_entry = MockConfigEntry(
        domain="adax",
        data=test_data,
        unique_id="8383838",
    )
    first_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: LOCAL,
        },
    )
    assert result2["type"] == FlowResultType.FORM

    test_data = {
        WIFI_SSID: "ssid",
        WIFI_PSWD: "pswd",
    }

    with patch("adax_local.AdaxConfig", autospec=True) as mock_client_class:
        client = mock_client_class.return_value
        client.configure_device.return_value = True
        client.device_ip = "192.168.1.4"
        client.access_token = "token"
        client.mac_id = "8383838"

        result = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            test_data,
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_local_connection_error(hass: HomeAssistant) -> None:
    """Test connection error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: LOCAL,
        },
    )
    assert result2["type"] == FlowResultType.FORM

    test_data = {
        WIFI_SSID: "ssid",
        WIFI_PSWD: "pswd",
    }

    with patch(
        "homeassistant.components.adax.config_flow.adax_local.AdaxConfig.configure_device",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            test_data,
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_local_heater_not_available(hass: HomeAssistant) -> None:
    """Test connection error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: LOCAL,
        },
    )
    assert result2["type"] == FlowResultType.FORM

    test_data = {
        WIFI_SSID: "ssid",
        WIFI_PSWD: "pswd",
    }

    with patch(
        "homeassistant.components.adax.config_flow.adax_local.AdaxConfig.configure_device",
        side_effect=adax_local.HeaterNotAvailable,
    ):
        result = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            test_data,
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "heater_not_available"


async def test_local_heater_not_found(hass: HomeAssistant) -> None:
    """Test connection error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: LOCAL,
        },
    )
    assert result2["type"] == FlowResultType.FORM

    test_data = {
        WIFI_SSID: "ssid",
        WIFI_PSWD: "pswd",
    }

    with patch(
        "homeassistant.components.adax.config_flow.adax_local.AdaxConfig.configure_device",
        side_effect=adax_local.HeaterNotFound,
    ):
        result = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            test_data,
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "heater_not_found"


async def test_local_invalid_wifi_cred(hass: HomeAssistant) -> None:
    """Test connection error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: LOCAL,
        },
    )
    assert result2["type"] == FlowResultType.FORM

    test_data = {
        WIFI_SSID: "ssid",
        WIFI_PSWD: "pswd",
    }

    with patch(
        "homeassistant.components.adax.config_flow.adax_local.AdaxConfig.configure_device",
        side_effect=adax_local.InvalidWifiCred,
    ):
        result = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            test_data,
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "invalid_auth"
