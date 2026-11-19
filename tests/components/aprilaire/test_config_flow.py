"""Tests for the Aprilaire config flow."""

from unittest.mock import AsyncMock, patch

from pyaprilaire.client import AprilaireClient, NackError, ResponseTimeoutError
from pyaprilaire.const import Attribute, FunctionalDomain, NackStatus
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.aprilaire.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture
def client() -> AprilaireClient:
    """Return a mock client."""
    return AsyncMock(AprilaireClient)


@pytest.mark.parametrize(
    ("side_effect", "return_value", "log_message"),
    [
        pytest.param(
            ResponseTimeoutError(FunctionalDomain.IDENTIFICATION, 2, 30),
            None,
            "Timed out after 30 seconds waiting for the MAC address",
            id="timeout",
        ),
        pytest.param(
            NackError(NackStatus.GENERIC_ERROR, NackStatus.GENERIC_ERROR.value),
            None,
            "Thermostat rejected the MAC address request: Request was NACKed"
            " with status GENERIC_ERROR (0x01)",
            id="nack",
        ),
        pytest.param(
            None,
            {},
            "MAC address missing from the thermostat response",
            id="missing",
        ),
    ],
)
async def test_config_flow_invalid_data(
    client: AprilaireClient,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    side_effect: Exception | None,
    return_value: dict[str, str] | None,
    log_message: str,
) -> None:
    """Test that the flow shows an error with invalid data and can recover."""
    client.read_mac_address_and_wait.side_effect = side_effect
    client.read_mac_address_and_wait.return_value = return_value

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch("pyaprilaire.client.AprilaireClient", return_value=client):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "localhost",
                "port": 8000,
            },
        )

    client.start_listen.assert_called_once()
    client.read_mac_address_and_wait.assert_called_once_with(30)
    client.read_thermostat_iaq_available_and_wait.assert_not_called()
    client.stop_listen.assert_called_once()
    assert log_message in caplog.text

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "connection_failed"}
    suggested_values = {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
    }
    assert suggested_values == {"host": "localhost", "port": 8000}

    client.data = {"mac_address": "1:2:3:4:5:6"}

    with (
        patch("pyaprilaire.client.AprilaireClient", return_value=client),
        patch(
            "homeassistant.components.aprilaire.async_setup_entry",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "localhost",
                "port": 8000,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "1:2:3:4:5:6"
    assert result["data"] == {"host": "localhost", "port": 8000}


async def test_config_flow_data(client: AprilaireClient, hass: HomeAssistant) -> None:
    """Test the config flow with valid data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    client.data = {"mac_address": "1:2:3:4:5:6"}

    with (
        patch("pyaprilaire.client.AprilaireClient", return_value=client),
        patch(
            "homeassistant.components.aprilaire.async_setup_entry",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "localhost",
                "port": 7000,
            },
        )
        await hass.async_block_till_done()

    client.start_listen.assert_called_once()
    client.read_mac_address_and_wait.assert_not_called()
    client.read_thermostat_iaq_available_and_wait.assert_called_once_with(30)
    client.read_sensors_and_wait.assert_called_once_with(30)
    client.stop_listen.assert_called_once()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "AprilAire"
    assert result["data"] == {
        "host": "localhost",
        "port": 7000,
    }
    assert result["result"].unique_id == "1:2:3:4:5:6"


async def test_config_flow_mac_address_request(
    client: AprilaireClient, hass: HomeAssistant
) -> None:
    """Test the flow requests the MAC address when the client has none cached."""
    data = {Attribute.MAC_ADDRESS: "01:02:03:04:05:06"}

    async def read_mac_address_and_wait(timeout: int) -> dict[str, str]:
        # The client delivers a response to the registered callback and the waiter
        client_class.call_args.args[2](data)
        return data

    client.read_mac_address_and_wait.side_effect = read_mac_address_and_wait

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with (
        patch(
            "pyaprilaire.client.AprilaireClient", return_value=client
        ) as client_class,
        patch(
            "homeassistant.components.aprilaire.async_setup_entry",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "localhost",
                "port": 7000,
            },
        )
        await hass.async_block_till_done()

    client.read_mac_address_and_wait.assert_called_once_with(30)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"host": "localhost", "port": 7000}
    assert result["result"].unique_id == "01:02:03:04:05:06"


async def test_config_flow_already_configured(
    client: AprilaireClient, hass: HomeAssistant
) -> None:
    """Test the config flow aborts when the device is already configured."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="1:2:3:4:5:6",
        data={"host": "localhost", "port": 7000},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    client.data = {"mac_address": "1:2:3:4:5:6"}

    with patch("pyaprilaire.client.AprilaireClient", return_value=client):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "localhost",
                "port": 7000,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_config_flow_optional_reads_fail(
    client: AprilaireClient, hass: HomeAssistant
) -> None:
    """Test the flow still succeeds when reads other than the MAC address fail."""
    client.data = {"mac_address": "1:2:3:4:5:6"}
    client.read_thermostat_iaq_available_and_wait.side_effect = ResponseTimeoutError(
        FunctionalDomain.CONTROL, 7, 30
    )
    client.read_sensors_and_wait.side_effect = NackError(
        NackStatus.GENERIC_ERROR, NackStatus.GENERIC_ERROR.value
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with (
        patch("pyaprilaire.client.AprilaireClient", return_value=client),
        patch(
            "homeassistant.components.aprilaire.async_setup_entry",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "localhost",
                "port": 7000,
            },
        )
        await hass.async_block_till_done()

    client.read_thermostat_status.assert_called_once()
    client.read_iaq_status.assert_called_once()
    assert result["type"] is FlowResultType.CREATE_ENTRY
