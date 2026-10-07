"""Test the Adax config flow."""

from unittest.mock import patch

import adax_local
import aiohttp
import pytest

from homeassistant import config_entries
from homeassistant.components.adax.const import (
    ACCOUNT_ID,
    CLOUD,
    CONNECTION_TYPE,
    DOMAIN,
    LOCAL,
    LOCAL_MANUAL,
    WIFI_PSWD,
    WIFI_SSID,
)
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_UNIQUE_ID,
)
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
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: CLOUD,
        },
    )
    assert result2["type"] is FlowResultType.FORM

    with (
        patch(
            "adax.get_adax_token",
            return_value="test_token",
        ),
        patch(
            "homeassistant.components.adax.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            TEST_DATA,
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
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
    assert result2["type"] is FlowResultType.FORM

    with patch(
        "adax.get_adax_token",
        return_value=None,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            TEST_DATA,
        )
    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "cannot_connect"}


async def test_flow_entry_already_exists(hass: HomeAssistant) -> None:
    """Test user input for config_entry that already exists."""

    first_entry = MockConfigEntry(
        domain=DOMAIN,
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
    assert result2["type"] is FlowResultType.FORM

    with patch("adax.get_adax_token", return_value="token"):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            TEST_DATA,
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "already_configured"


# local API:


async def test_local_create_entry(hass: HomeAssistant) -> None:
    """Test create entry from user input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: LOCAL,
        },
    )
    assert result2["type"] is FlowResultType.FORM

    test_data = {
        WIFI_SSID: "ssid",
        WIFI_PSWD: "pswd",
    }

    with (
        patch(
            "homeassistant.components.adax.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.adax.config_flow.adax_local.AdaxConfig",
            autospec=True,
        ) as mock_client_class,
    ):
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
    assert result["type"] is FlowResultType.CREATE_ENTRY
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
        domain=DOMAIN,
        data=test_data,
        unique_id="8383838",
    )
    first_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: LOCAL,
        },
    )
    assert result2["type"] is FlowResultType.FORM

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

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_local_connection_error(hass: HomeAssistant) -> None:
    """Test connection error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: LOCAL,
        },
    )
    assert result2["type"] is FlowResultType.FORM

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

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_local_heater_not_available(hass: HomeAssistant) -> None:
    """Test connection error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: LOCAL,
        },
    )
    assert result2["type"] is FlowResultType.FORM

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

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "heater_not_available"


async def test_local_heater_not_found(hass: HomeAssistant) -> None:
    """Test connection error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: LOCAL,
        },
    )
    assert result2["type"] is FlowResultType.FORM

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

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "heater_not_found"


async def test_local_invalid_wifi_cred(hass: HomeAssistant) -> None:
    """Test connection error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: LOCAL,
        },
    )
    assert result2["type"] is FlowResultType.FORM

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

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_auth"


async def test_form_local_manual_success(hass: HomeAssistant) -> None:
    """Test successful manual local configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONNECTION_TYPE: LOCAL_MANUAL},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "local_manual"

    expected_unique_id = str(int("AABBCCDDEEFF", 16))

    with (
        patch(
            "homeassistant.components.adax.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.adax.config_flow.AdaxLocal.get_status",
            return_value={"target_temperature": 20.0, "current_temperature": 21.0},
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "192.168.1.150",
                CONF_MAC: "AA:BB:CC:DD:EE:FF",
                CONF_TOKEN: "abcdef123456",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_unique_id
    assert result["data"] == {
        CONF_IP_ADDRESS: "192.168.1.150",
        CONF_TOKEN: "abcdef123456",
        CONF_UNIQUE_ID: expected_unique_id,
        CONNECTION_TYPE: LOCAL,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_local_manual_invalid_mac(hass: HomeAssistant) -> None:
    """Test validation failure on invalid MAC address inputs."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONNECTION_TYPE: LOCAL_MANUAL},
    )
    assert result["step_id"] == "local_manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IP_ADDRESS: "192.168.1.150",
            CONF_MAC: "not-a-mac",
            CONF_TOKEN: "abcdef123456",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_MAC: "invalid_mac"}


async def test_form_local_manual_cannot_connect(hass: HomeAssistant) -> None:
    """Test error handling when heater cannot be contacted."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONNECTION_TYPE: LOCAL_MANUAL},
    )

    with patch(
        "homeassistant.components.adax.config_flow.AdaxLocal.get_status",
        return_value={"target_temperature": None, "current_temperature": None},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "192.168.1.150",
                CONF_MAC: "AA:BB:CC:DD:EE:FF",
                CONF_TOKEN: "wrong_token",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (aiohttp.ClientError, "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_local_manual_exceptions(
    hass: HomeAssistant, side_effect: type[Exception], expected_error: str
) -> None:
    """Test handling of transport and unexpected exceptions when contacting heater."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONNECTION_TYPE: LOCAL_MANUAL},
    )
    assert result["step_id"] == "local_manual"

    with patch(
        "homeassistant.components.adax.config_flow.AdaxLocal.get_status",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "192.168.1.150",
                CONF_MAC: "AA:BB:CC:DD:EE:FF",
                CONF_TOKEN: "abcdef123456",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


async def test_form_local_manual_recover_after_exception(
    hass: HomeAssistant,
) -> None:
    """Test flow can recover after a connection failure in local manual mode."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONNECTION_TYPE: LOCAL_MANUAL},
    )

    with patch(
        "homeassistant.components.adax.config_flow.AdaxLocal.get_status",
        side_effect=aiohttp.ClientError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "192.168.1.150",
                CONF_MAC: "AA:BB:CC:DD:EE:FF",
                CONF_TOKEN: "abcdef123456",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    expected_unique_id = str(int("AABBCCDDEEFF", 16))
    with (
        patch(
            "homeassistant.components.adax.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.adax.config_flow.AdaxLocal.get_status",
            return_value={"target_temperature": 20.0, "current_temperature": 21.0},
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "192.168.1.150",
                CONF_MAC: "AA:BB:CC:DD:EE:FF",
                CONF_TOKEN: "abcdef123456",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == expected_unique_id


async def test_form_local_manual_already_configured(hass: HomeAssistant) -> None:
    """Test aborting if device is already configured."""
    mac = "AA:BB:CC:DD:EE:FF"
    unique_id = str(int("AABBCCDDEEFF", 16))

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=unique_id,
        data={
            CONF_IP_ADDRESS: "192.168.1.100",
            CONF_TOKEN: "existing_token",
            CONF_UNIQUE_ID: unique_id,
            CONNECTION_TYPE: LOCAL,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONNECTION_TYPE: LOCAL_MANUAL},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_IP_ADDRESS: "192.168.1.150",
            CONF_MAC: mac,
            CONF_TOKEN: "abcdef123456",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
