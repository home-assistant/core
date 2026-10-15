"""Tests for the Aprilaire config flow."""

from unittest.mock import AsyncMock, Mock, patch

from pyaprilaire.client import AprilaireClient, NackError, ResponseTimeoutError
from pyaprilaire.const import FunctionalDomain, NackStatus
import pytest

from homeassistant.components.aprilaire.config_flow import (
    STEP_USER_DATA_SCHEMA,
    AprilaireConfigFlow,
)
from homeassistant.core import HomeAssistant


@pytest.fixture
def client() -> AprilaireClient:
    """Return a mock client."""
    return AsyncMock(AprilaireClient)


async def test_user_input_step() -> None:
    """Test the user input step."""

    show_form_mock = Mock()

    config_flow = AprilaireConfigFlow()
    config_flow.async_show_form = show_form_mock

    await config_flow.async_step_user(None)

    show_form_mock.assert_called_once_with(
        step_id="user", data_schema=STEP_USER_DATA_SCHEMA
    )


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
    caplog: pytest.LogCaptureFixture,
    side_effect: Exception | None,
    return_value: dict[str, str] | None,
    log_message: str,
) -> None:
    """Test that the flow shows an error when the MAC address can't be read."""

    client.read_mac_address_and_wait.side_effect = side_effect
    client.read_mac_address_and_wait.return_value = return_value

    show_form_mock = Mock()
    set_unique_id_mock = AsyncMock()
    async_abort_entries_match_mock = Mock()

    config_flow = AprilaireConfigFlow()
    config_flow.async_show_form = show_form_mock
    config_flow.async_set_unique_id = set_unique_id_mock
    config_flow._async_abort_entries_match = async_abort_entries_match_mock

    with patch("pyaprilaire.client.AprilaireClient", return_value=client):
        await config_flow.async_step_user(
            {
                "host": "localhost",
                "port": 7000,
            }
        )

    client.start_listen.assert_called_once()
    client.read_mac_address_and_wait.assert_called_once_with(30)
    client.read_thermostat_iaq_available_and_wait.assert_not_called()
    client.stop_listen.assert_called_once()
    assert log_message in caplog.text

    show_form_mock.assert_called_once_with(
        step_id="user",
        data_schema=STEP_USER_DATA_SCHEMA,
        errors={"base": "connection_failed"},
    )


async def test_config_flow_data(client: AprilaireClient, hass: HomeAssistant) -> None:
    """Test the config flow with valid data."""

    client.data = {"mac_address": "01:02:03:04:05:06"}

    show_form_mock = Mock()
    set_unique_id_mock = AsyncMock()
    abort_if_unique_id_configured_mock = Mock()
    create_entry_mock = Mock()

    config_flow = AprilaireConfigFlow()
    config_flow.hass = hass
    config_flow.async_show_form = show_form_mock
    config_flow.async_set_unique_id = set_unique_id_mock
    config_flow._abort_if_unique_id_configured = abort_if_unique_id_configured_mock
    config_flow.async_create_entry = create_entry_mock

    client.read_mac_address_and_wait.return_value = {"mac_address": "01:02:03:04:05:06"}

    with patch("pyaprilaire.client.AprilaireClient", return_value=client):
        await config_flow.async_step_user(
            {
                "host": "localhost",
                "port": 7000,
            }
        )

    client.start_listen.assert_called_once()
    client.read_mac_address_and_wait.assert_not_called()
    client.read_thermostat_iaq_available_and_wait.assert_called_once_with(30)
    client.read_sensors_and_wait.assert_called_once_with(30)
    client.stop_listen.assert_called_once()

    set_unique_id_mock.assert_called_once_with("01:02:03:04:05:06")
    abort_if_unique_id_configured_mock.assert_called_once()

    create_entry_mock.assert_called_once_with(
        title="AprilAire",
        data={
            "host": "localhost",
            "port": 7000,
        },
    )


async def test_config_flow_optional_reads_fail(
    client: AprilaireClient, hass: HomeAssistant
) -> None:
    """Test the flow still succeeds when reads other than the MAC address fail."""

    create_entry_mock = Mock()

    config_flow = AprilaireConfigFlow()
    config_flow.hass = hass
    config_flow.async_set_unique_id = AsyncMock()
    config_flow._abort_if_unique_id_configured = Mock()
    config_flow.async_create_entry = create_entry_mock

    client.data = {"mac_address": "01:02:03:04:05:06"}
    client.read_mac_address_and_wait.return_value = {"mac_address": "01:02:03:04:05:06"}
    client.read_thermostat_iaq_available_and_wait.side_effect = ResponseTimeoutError(
        FunctionalDomain.CONTROL, 7, 30
    )
    client.read_sensors_and_wait.side_effect = NackError(
        NackStatus.GENERIC_ERROR, NackStatus.GENERIC_ERROR.value
    )

    with patch("pyaprilaire.client.AprilaireClient", return_value=client):
        await config_flow.async_step_user({"host": "localhost", "port": 7000})

    client.read_thermostat_status.assert_called_once()
    client.read_iaq_status.assert_called_once()
    create_entry_mock.assert_called_once()
