"""Tests for the Peblar integration services."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

from peblar import (
    PeblarAuthenticationError,
    PeblarConnectionError,
    PeblarError,
    PeblarRfidToken,
    PeblarVehicleToken,
)
import pytest
import voluptuous as vol

from homeassistant.components.peblar.const import DOMAIN
from homeassistant.components.peblar.services import (
    SERVICE_ADD_RFID_TOKEN,
    SERVICE_ADD_VEHICLE_TOKEN,
    SERVICE_AUTHORIZE_CHARGE_SESSION,
    SERVICE_DELETE_RFID_TOKEN,
    SERVICE_DELETE_VEHICLE_TOKEN,
    SERVICE_GET_METER_HISTORY,
    SERVICE_LIST_RFID_TOKENS,
    SERVICE_LIST_VEHICLE_TOKENS,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from tests.common import MockConfigEntry


async def test_services_registered_on_setup(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test that RFID services are registered when entry is loaded."""
    assert hass.services.has_service(DOMAIN, SERVICE_LIST_RFID_TOKENS)
    assert hass.services.has_service(DOMAIN, SERVICE_ADD_RFID_TOKEN)
    assert hass.services.has_service(DOMAIN, SERVICE_DELETE_RFID_TOKEN)


async def test_services_survive_entry_unload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test RFID services stay registered when the last Peblar entry unloads."""
    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_LIST_RFID_TOKENS)
    assert hass.services.has_service(DOMAIN, SERVICE_ADD_RFID_TOKEN)
    assert hass.services.has_service(DOMAIN, SERVICE_DELETE_RFID_TOKEN)


async def test_list_rfid_tokens(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test list_rfid_tokens returns token list."""
    mock_peblar.rfid_tokens.return_value = [
        PeblarRfidToken(
            rfid_token_uid="AA:BB:CC:DD",
            rfid_token_description="My Card",
        ),
        PeblarRfidToken(
            rfid_token_uid="11:22:33:44",
            rfid_token_description="Work Badge",
        ),
    ]

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_LIST_RFID_TOKENS,
        {"config_entry_id": init_integration.entry_id},
        blocking=True,
        return_response=True,
    )

    assert result == {
        "tokens": [
            {"uid": "AA:BB:CC:DD", "description": "My Card"},
            {"uid": "11:22:33:44", "description": "Work Badge"},
        ]
    }
    mock_peblar.rfid_tokens.assert_called_once_with()


async def test_add_rfid_token(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test add_rfid_token calls library with correct args."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_RFID_TOKEN,
        {
            "config_entry_id": init_integration.entry_id,
            "uid": "AA:BB:CC:DD",
            "description": "My Card",
        },
        blocking=True,
    )

    mock_peblar.add_rfid_token.assert_called_once_with(
        rfid_token_uid="AA:BB:CC:DD",
        rfid_token_description="My Card",
    )


async def test_delete_rfid_token(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test delete_rfid_token calls library with correct args."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_DELETE_RFID_TOKEN,
        {
            "config_entry_id": init_integration.entry_id,
            "uid": "AA:BB:CC:DD",
        },
        blocking=True,
    )

    mock_peblar.delete_rfid_token.assert_called_once_with(uid="AA:BB:CC:DD")


async def test_unloaded_config_entry_raises(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_peblar: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test service raises ServiceValidationError for an unloaded entry."""
    second_entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry.data,
        unique_id="second-charger",
    )
    second_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(second_entry.entry_id)
    await hass.async_block_till_done()

    await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_LIST_RFID_TOKENS,
            {"config_entry_id": init_integration.entry_id},
            blocking=True,
            return_response=True,
        )

    assert excinfo.value.translation_key == "service_config_entry_not_loaded"


SERVICE_CALLS: list[tuple[str, str, dict[str, Any]]] = [
    (SERVICE_LIST_RFID_TOKENS, "rfid_tokens", {}),
    (
        SERVICE_ADD_RFID_TOKEN,
        "add_rfid_token",
        {"uid": "AA:BB:CC:DD", "description": "My Card"},
    ),
    (SERVICE_DELETE_RFID_TOKEN, "delete_rfid_token", {"uid": "AA:BB:CC:DD"}),
]

# The services that answer over the same error handling, whether or not
# they touch the RFID list.
FAILING_SERVICE_CALLS: list[tuple[str, str, dict[str, Any]]] = [
    *SERVICE_CALLS,
    (SERVICE_GET_METER_HISTORY, "meter_history", {}),
]

RESPONDING_SERVICES = {SERVICE_LIST_RFID_TOKENS, SERVICE_GET_METER_HISTORY}


@pytest.mark.parametrize(
    ("service", "method_name", "service_data"), FAILING_SERVICE_CALLS
)
@pytest.mark.parametrize(
    ("error", "translation_key"),
    [
        (PeblarConnectionError("Could not connect"), "communication_error"),
        (PeblarError("Something went wrong"), "unknown_error"),
    ],
)
async def test_service_communication_error(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    init_integration: MockConfigEntry,
    service: str,
    method_name: str,
    service_data: dict[str, Any],
    error: Exception,
    translation_key: str,
) -> None:
    """Test Peblar library errors are translated into Home Assistant errors."""
    getattr(mock_peblar, method_name).side_effect = error

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            service,
            {"config_entry_id": init_integration.entry_id, **service_data},
            blocking=True,
            return_response=service in RESPONDING_SERVICES,
        )

    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == translation_key
    assert excinfo.value.translation_placeholders == {"error": str(error)}


@pytest.mark.parametrize(
    ("service", "method_name", "service_data"), FAILING_SERVICE_CALLS
)
async def test_service_authentication_error(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    init_integration: MockConfigEntry,
    service: str,
    method_name: str,
    service_data: dict[str, Any],
) -> None:
    """Test an authentication error triggers a reauthentication flow."""
    getattr(mock_peblar, method_name).side_effect = PeblarAuthenticationError(
        "Authentication error"
    )
    mock_peblar.login.side_effect = PeblarAuthenticationError("Authentication error")

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            service,
            {"config_entry_id": init_integration.entry_id, **service_data},
            blocking=True,
            return_response=service in RESPONDING_SERVICES,
        )

    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == "authentication_error"
    assert not excinfo.value.translation_placeholders

    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
    assert flows[0]["context"].get("source") == SOURCE_REAUTH
    assert flows[0]["context"].get("entry_id") == init_integration.entry_id


async def test_invalid_config_entry_raises(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test service raises ServiceValidationError for unknown entry ID."""
    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_LIST_RFID_TOKENS,
            {"config_entry_id": "nonexistent-entry-id"},
            blocking=True,
            return_response=True,
        )

    assert excinfo.value.translation_key == "service_config_entry_not_found"


@pytest.mark.parametrize(("service", "method_name", "service_data"), SERVICE_CALLS)
@pytest.mark.parametrize("mock_peblar", [{"HwHasRfid": False}], indirect=True)
async def test_charger_without_rfid_reader(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    service: str,
    method_name: str,
    service_data: dict[str, Any],
) -> None:
    """A charger without a reader has no standalone list to manage."""
    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            service,
            {"config_entry_id": init_integration.entry_id, **service_data},
            blocking=True,
            return_response=service == SERVICE_LIST_RFID_TOKENS,
        )

    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == "no_rfid_hardware"


async def test_list_vehicle_tokens(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test list_vehicle_tokens returns the vehicles on the charger."""
    mock_peblar.vehicle_tokens.return_value = [
        PeblarVehicleToken(evcc_id="EVCC-1234", alias="The blue one"),
        PeblarVehicleToken(evcc_id="EVCC-5678", alias="The other one"),
    ]

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_LIST_VEHICLE_TOKENS,
        {"config_entry_id": init_integration.entry_id},
        blocking=True,
        return_response=True,
    )

    assert result == {
        "vehicles": [
            {"evcc_id": "EVCC-1234", "alias": "The blue one"},
            {"evcc_id": "EVCC-5678", "alias": "The other one"},
        ]
    }
    mock_peblar.vehicle_tokens.assert_called_once_with()


async def test_add_vehicle_token(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test add_vehicle_token calls the library with the right arguments."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_ADD_VEHICLE_TOKEN,
        {
            "config_entry_id": init_integration.entry_id,
            "evcc_id": "EVCC-1234",
            "alias": "The blue one",
        },
        blocking=True,
    )

    mock_peblar.add_vehicle_token.assert_called_once_with(
        evcc_id="EVCC-1234",
        alias="The blue one",
    )


async def test_delete_vehicle_token(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test delete_vehicle_token calls the library with the right arguments."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_DELETE_VEHICLE_TOKEN,
        {
            "config_entry_id": init_integration.entry_id,
            "evcc_id": "EVCC-1234",
        },
        blocking=True,
    )

    mock_peblar.delete_vehicle_token.assert_called_once_with(evcc_id="EVCC-1234")


AUTOCHARGE_CALLS: list[tuple[str, dict[str, Any]]] = [
    (SERVICE_LIST_VEHICLE_TOKENS, {}),
    (SERVICE_ADD_VEHICLE_TOKEN, {"evcc_id": "EVCC-1234", "alias": "The blue one"}),
    (SERVICE_DELETE_VEHICLE_TOKEN, {"evcc_id": "EVCC-1234"}),
]


@pytest.mark.parametrize("mock_peblar", [{"HwHasRfid": False}], indirect=True)
@pytest.mark.parametrize(("service", "service_data"), AUTOCHARGE_CALLS)
@pytest.mark.usefixtures("mock_peblar")
async def test_autocharge_does_not_need_an_rfid_reader(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    service: str,
    service_data: dict[str, Any],
) -> None:
    """Test the autocharge list is a separate one from the RFID list.

    Autocharge identifies a car by what its own controller presents, so it
    has nothing to do with the reader.
    """
    await hass.services.async_call(
        DOMAIN,
        service,
        {"config_entry_id": init_integration.entry_id, **service_data},
        blocking=True,
        return_response=service == SERVICE_LIST_VEHICLE_TOKENS,
    )


@pytest.mark.parametrize("mock_peblar", [{"HwHasPlc": False}], indirect=True)
@pytest.mark.parametrize(("service", "service_data"), AUTOCHARGE_CALLS)
@pytest.mark.usefixtures("mock_peblar")
async def test_autocharge_needs_power_line_communication(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    service: str,
    service_data: dict[str, Any],
) -> None:
    """Test a charger that cannot do autocharge is turned away.

    Checked against a charger without the hardware: it answers 200 with
    null on the list, and 403 on adding and deleting. Letting that come
    back as a failed request tells the user nothing.
    """
    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            service,
            {"config_entry_id": init_integration.entry_id, **service_data},
            blocking=True,
            return_response=service == SERVICE_LIST_VEHICLE_TOKENS,
        )

    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == "no_autocharge_hardware"


@pytest.mark.parametrize(
    ("service_data", "expected"),
    [
        ({"uid": "0123456789ABCD"}, {"token": "0123456789ABCD", "name": None}),
        ({"description": "My card"}, {"token": None, "name": "My card"}),
    ],
    ids=["by uid", "by description"],
)
async def test_authorize_charge_session(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    init_integration: MockConfigEntry,
    service_data: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    """Test the token can be presented by either of the two names for it."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_AUTHORIZE_CHARGE_SESSION,
        {"config_entry_id": init_integration.entry_id, **service_data},
        blocking=True,
    )

    mock_peblar.rest_api.return_value.authorize_charge_session.assert_called_once_with(
        **expected
    )


@pytest.mark.parametrize(
    "service_data",
    [
        {},
        {"uid": "0123456789ABCD", "description": "My card"},
    ],
    ids=["neither", "both"],
)
async def test_authorize_charge_session_needs_exactly_one_token(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    init_integration: MockConfigEntry,
    service_data: dict[str, Any],
) -> None:
    """Test the charger is told which token to present, and only one."""
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_AUTHORIZE_CHARGE_SESSION,
            {"config_entry_id": init_integration.entry_id, **service_data},
            blocking=True,
        )

    mock_peblar.rest_api.return_value.authorize_charge_session.assert_not_called()


@pytest.mark.parametrize(
    ("mock_peblar", "translation_key"),
    [
        ({"HwHasRfid": False}, "no_rfid_hardware"),
        ({"SeccOcppActive": True}, "managed_by_backoffice"),
        ({"SessionManagerChargeWithoutAuth": True}, "authorization_not_required"),
    ],
    ids=["no reader", "managed over OCPP", "no authorization needed"],
    indirect=["mock_peblar"],
)
async def test_authorize_charge_session_is_refused(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    init_integration: MockConfigEntry,
    translation_key: str,
) -> None:
    """Test a charger that cannot or need not authorize is turned away.

    The API refuses this outright on a charger managed over OCPP, and a
    charger that charges without authorization has nothing to authorize.
    """
    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_AUTHORIZE_CHARGE_SESSION,
            {
                "config_entry_id": init_integration.entry_id,
                "uid": "0123456789ABCD",
            },
            blocking=True,
        )

    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == translation_key
    mock_peblar.rest_api.return_value.authorize_charge_session.assert_not_called()


async def test_get_meter_history(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test the meter history comes back as sessions.

    The second session in the fixture is the one still running: it has no
    end, and so no energy total to report for it either.
    """
    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_METER_HISTORY,
        {"config_entry_id": init_integration.entry_id},
        blocking=True,
        return_response=True,
    )

    assert result == {
        "corrupted": False,
        "sessions": [
            {
                "session_number": 1,
                "uid": "AA:BB:CC:DD",
                "start_time": "2026-01-22T12:00:00+00:00",
                "end_time": "2026-01-22T19:00:00+00:00",
                "start_energy_kwh": 1.0,
                "end_energy_kwh": 8.5,
                "energy_kwh": 7.5,
                "checksum": 42,
                "corrupted": True,
            },
            {
                "session_number": 2,
                "uid": None,
                "start_time": "2026-01-23T12:00:00+00:00",
                "end_time": None,
                "start_energy_kwh": 8.5,
                "end_energy_kwh": None,
                "energy_kwh": None,
                "checksum": 43,
                "corrupted": False,
            },
        ],
    }
    mock_peblar.meter_history.assert_called_once_with(start=None, stop=None)


async def test_get_meter_history_without_every_checksum_outcome(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test a session the charger returned no checksum outcome for.

    The outcomes come back as a list of their own, so a charger that
    returns fewer of them than it returns sessions leaves the last ones
    unanswered.
    """
    mock_peblar.meter_history.return_value.corrupted_session = [False]

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_METER_HISTORY,
        {"config_entry_id": init_integration.entry_id},
        blocking=True,
        return_response=True,
    )

    assert [session["corrupted"] for session in result["sessions"]] == [False, None]


@pytest.mark.parametrize("mock_peblar", [{"HwHasRfid": False}], indirect=True)
async def test_get_meter_history_needs_no_rfid_reader(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test the meter records every session, tokens or no tokens."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_METER_HISTORY,
        {"config_entry_id": init_integration.entry_id},
        blocking=True,
        return_response=True,
    )

    mock_peblar.meter_history.assert_called_once_with(start=None, stop=None)


@pytest.mark.parametrize(
    ("after", "before"),
    [
        ("2026-01-22T13:00:00+01:00", "2026-01-23T13:00:00+01:00"),
        ("2026-01-22 13:00:00", "2026-01-23 13:00:00"),
    ],
    ids=["with offset", "naive"],
)
async def test_get_meter_history_time_range(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    init_integration: MockConfigEntry,
    after: str,
    before: str,
) -> None:
    """Test both ends of the range reach the charger, as UTC.

    A moment without an offset is the one the user typed into the
    frontend, so it is read in Home Assistant's own timezone rather than
    handed to the charger for it to interpret.
    """
    await hass.config.async_set_time_zone("Europe/Amsterdam")

    await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_METER_HISTORY,
        {
            "config_entry_id": init_integration.entry_id,
            "after": after,
            "before": before,
        },
        blocking=True,
        return_response=True,
    )

    mock_peblar.meter_history.assert_called_once_with(
        start=datetime(2026, 1, 22, 12, tzinfo=UTC),
        stop=datetime(2026, 1, 23, 12, tzinfo=UTC),
    )
