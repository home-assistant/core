"""Test fixtures for home_connect."""

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
import copy
import time
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from aiohomeconnect.client import Client as HomeConnectClient
from aiohomeconnect.model import (
    ArrayOfCommands,
    ArrayOfEvents,
    ArrayOfHomeAppliances,
    ArrayOfOptions,
    ArrayOfPrograms,
    ArrayOfSettings,
    Event,
    EventKey,
    EventMessage,
    EventType,
    GetSetting,
    HomeAppliance,
    Option,
    Program,
    ProgramDefinition,
    ProgramKey,
    SettingKey,
)
from aiohomeconnect.model.error import HomeConnectApiError, HomeConnectError
from aiohomeconnect.model.program import EnumerateProgram
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.home_connect.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import MOCK_AVAILABLE_COMMANDS, MOCK_PROGRAMS, MOCK_SETTINGS, MOCK_STATUS

from tests.common import MockConfigEntry, load_fixture

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
FAKE_ACCESS_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ"
    ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
)
FAKE_REFRESH_TOKEN = "some-refresh-token"
FAKE_AUTH_IMPL = "conftest-imported-cred"

SERVER_ACCESS_TOKEN = {
    "refresh_token": "server-refresh-token",
    "access_token": "server-access-token",
    "type": "Bearer",
    "expires_in": 60,
}


@pytest.fixture(name="token_expiration_time")
def mock_token_expiration_time() -> float:
    """Fixture for expiration time of the config entry auth token."""
    return time.time() + 86400


@pytest.fixture(name="token_entry")
def mock_token_entry(token_expiration_time: float) -> dict[str, Any]:
    """Fixture for OAuth 'token' data for a ConfigEntry."""
    return {
        "refresh_token": FAKE_REFRESH_TOKEN,
        "access_token": FAKE_ACCESS_TOKEN,
        "type": "Bearer",
        "expires_at": token_expiration_time,
    }


@pytest.fixture(name="config_entry")
def mock_config_entry(token_entry: dict[str, Any]) -> MockConfigEntry:
    """Fixture for a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": FAKE_AUTH_IMPL,
            "token": token_entry,
        },
        minor_version=3,
        unique_id="1234567890",
    )


@pytest.fixture(name="config_entry_v1_1")
def mock_config_entry_v1_1(token_entry: dict[str, Any]) -> MockConfigEntry:
    """Fixture for a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": FAKE_AUTH_IMPL,
            "token": token_entry,
        },
        minor_version=1,
    )


@pytest.fixture(name="config_entry_v1_2")
def mock_config_entry_v1_2(token_entry: dict[str, Any]) -> MockConfigEntry:
    """Fixture for a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": FAKE_AUTH_IMPL,
            "token": token_entry,
        },
        minor_version=2,
    )


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
        FAKE_AUTH_IMPL,
    )


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return []


@pytest.fixture(name="integration_setup")
async def mock_integration_setup(
    hass: HomeAssistant,
    platforms: list[Platform],
    config_entry: MockConfigEntry,
) -> Callable[[MagicMock], Awaitable[bool]]:
    """Fixture to set up the integration."""
    config_entry.add_to_hass(hass)

    async def run(client: MagicMock) -> bool:
        with (
            patch("homeassistant.components.home_connect.PLATFORMS", platforms),
            patch(
                "homeassistant.components.home_connect.HomeConnectClient"
            ) as client_mock,
        ):
            client_mock.return_value = client
            result = await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()
        return result

    return run


def _get_set_program_side_effect(
    event_queue: asyncio.Queue[list[EventMessage]], event_key: EventKey
):
    """Set program side effect."""

    async def set_program_side_effect(ha_id: str, *_, **kwargs) -> None:
        await event_queue.put(
            [
                EventMessage(
                    ha_id,
                    EventType.NOTIFY,
                    ArrayOfEvents(
                        [
                            Event(
                                key=event_key,
                                raw_key=event_key.value,
                                timestamp=0,
                                level="",
                                handling="",
                                value=str(kwargs["program_key"]),
                            ),
                            *[
                                Event(
                                    key=(option_event := EventKey(option.key)),
                                    raw_key=option_event.value,
                                    timestamp=0,
                                    level="",
                                    handling="",
                                    value=str(option.key),
                                )
                                for option in cast(
                                    list[Option], kwargs.get("options", [])
                                )
                            ],
                        ]
                    ),
                ),
            ]
        )

    return set_program_side_effect


def _get_set_setting_side_effect(
    event_queue: asyncio.Queue[list[EventMessage]],
):
    """Set settings side effect."""

    async def set_settings_side_effect(ha_id: str, *_, **kwargs) -> None:
        event_key = EventKey(kwargs["setting_key"])
        await event_queue.put(
            [
                EventMessage(
                    ha_id,
                    EventType.NOTIFY,
                    ArrayOfEvents(
                        [
                            Event(
                                key=event_key,
                                raw_key=event_key.value,
                                timestamp=0,
                                level="",
                                handling="",
                                value=kwargs["value"],
                            )
                        ]
                    ),
                ),
            ]
        )

    return set_settings_side_effect


def _get_set_program_options_side_effect(
    event_queue: asyncio.Queue[list[EventMessage]],
):
    """Set programs side effect."""

    async def set_program_options_side_effect(ha_id: str, *_, **kwargs) -> None:
        await event_queue.put(
            [
                EventMessage(
                    ha_id,
                    EventType.NOTIFY,
                    ArrayOfEvents(
                        [
                            Event(
                                key=EventKey(option.key),
                                raw_key=option.key.value,
                                timestamp=0,
                                level="",
                                handling="",
                                value=option.value,
                            )
                            for option in (
                                cast(ArrayOfOptions, kwargs["array_of_options"]).options
                                if "array_of_options" in kwargs
                                else [
                                    Option(
                                        kwargs["option_key"],
                                        kwargs["value"],
                                        unit=kwargs["unit"],
                                    )
                                ]
                            )
                        ]
                    ),
                ),
            ]
        )

    return set_program_options_side_effect


@pytest.fixture(name="client")
def mock_client(
    appliances: list[HomeAppliance],
    appliance: HomeAppliance | None,
    request: pytest.FixtureRequest,
) -> MagicMock:
    """Fixture to mock Client from HomeConnect."""

    mock = MagicMock(
        autospec=HomeConnectClient,
    )

    event_queue: asyncio.Queue[list[EventMessage]] = asyncio.Queue()

    async def add_events(events: list[EventMessage]) -> None:
        await event_queue.put(events)

    mock.add_events = add_events

    async def set_program_option_side_effect(ha_id: str, *_, **kwargs) -> None:
        event_key = EventKey(kwargs["option_key"])
        await event_queue.put(
            [
                EventMessage(
                    ha_id,
                    EventType.NOTIFY,
                    ArrayOfEvents(
                        [
                            Event(
                                key=event_key,
                                raw_key=event_key.value,
                                timestamp=0,
                                level="",
                                handling="",
                                value=kwargs["value"],
                            )
                        ]
                    ),
                ),
            ]
        )

    appliances = [appliance] if appliance else appliances

    async def stream_all_events() -> AsyncGenerator[EventMessage]:
        """Mock stream_all_events."""
        while True:
            for event in await event_queue.get():
                yield event

    mock.get_home_appliances = AsyncMock(return_value=ArrayOfHomeAppliances(appliances))

    def _get_specific_appliance_side_effect(ha_id: str) -> HomeAppliance:
        """Get specific appliance side effect."""
        for appliance_ in appliances:
            if appliance_.ha_id == ha_id:
                return appliance_
        raise HomeConnectApiError("error.key", "error description")

    mock.get_specific_appliance = AsyncMock(
        side_effect=_get_specific_appliance_side_effect
    )
    mock.stream_all_events = stream_all_events

    async def _get_all_programs_side_effect(ha_id: str) -> ArrayOfPrograms:
        """Get all programs."""
        appliance_type = next(
            appliance for appliance in appliances if appliance.ha_id == ha_id
        ).type
        if appliance_type not in MOCK_PROGRAMS:
            raise HomeConnectApiError("error.key", "error description")

        return ArrayOfPrograms(
            [
                EnumerateProgram.from_dict(program)
                for program in MOCK_PROGRAMS[appliance_type]["data"]["programs"]
            ],
            Program.from_dict(MOCK_PROGRAMS[appliance_type]["data"]["programs"][0]),
            Program.from_dict(MOCK_PROGRAMS[appliance_type]["data"]["programs"][0]),
        )

    async def _get_settings_side_effect(ha_id: str) -> ArrayOfSettings:
        """Get settings."""
        return ArrayOfSettings.from_dict(
            MOCK_SETTINGS.get(
                next(
                    appliance for appliance in appliances if appliance.ha_id == ha_id
                ).type,
                {},
            ).get("data", {"settings": []})
        )

    async def _get_setting_side_effect(ha_id: str, setting_key: SettingKey):
        """Get setting."""
        for appliance_ in appliances:
            if appliance_.ha_id == ha_id:
                settings = MOCK_SETTINGS.get(
                    appliance_.type,
                    {},
                ).get("data", {"settings": []})
                for setting_dict in cast(list[dict], settings["settings"]):
                    if setting_dict["key"] == setting_key:
                        return GetSetting.from_dict(setting_dict)
        raise HomeConnectApiError("error.key", "error description")

    async def _get_available_commands_side_effect(ha_id: str) -> ArrayOfCommands:
        """Get available commands."""
        for appliance_ in appliances:
            if appliance_.ha_id == ha_id and appliance_.type in MOCK_AVAILABLE_COMMANDS:
                return ArrayOfCommands.from_dict(
                    MOCK_AVAILABLE_COMMANDS[appliance_.type]
                )
        raise HomeConnectApiError("error.key", "error description")

    mock.start_program = AsyncMock(
        side_effect=_get_set_program_side_effect(
            event_queue, EventKey.BSH_COMMON_ROOT_ACTIVE_PROGRAM
        )
    )
    mock.set_selected_program = AsyncMock(
        side_effect=_get_set_program_side_effect(
            event_queue, EventKey.BSH_COMMON_ROOT_SELECTED_PROGRAM
        ),
    )
    mock.stop_program = AsyncMock()
    mock.set_active_program_option = AsyncMock(
        side_effect=_get_set_program_options_side_effect(event_queue),
    )
    mock.set_active_program_options = AsyncMock(
        side_effect=_get_set_program_options_side_effect(event_queue),
    )
    mock.set_selected_program_option = AsyncMock(
        side_effect=_get_set_program_options_side_effect(event_queue),
    )
    mock.set_selected_program_options = AsyncMock(
        side_effect=_get_set_program_options_side_effect(event_queue),
    )
    mock.set_setting = AsyncMock(
        side_effect=_get_set_setting_side_effect(event_queue),
    )
    mock.get_settings = AsyncMock(side_effect=_get_settings_side_effect)
    mock.get_setting = AsyncMock(side_effect=_get_setting_side_effect)
    mock.get_status = AsyncMock(return_value=copy.deepcopy(MOCK_STATUS))
    mock.get_all_programs = AsyncMock(side_effect=_get_all_programs_side_effect)
    mock.get_available_commands = AsyncMock(
        side_effect=_get_available_commands_side_effect
    )
    mock.put_command = AsyncMock()
    mock.get_available_program = AsyncMock(
        return_value=ProgramDefinition(ProgramKey.UNKNOWN, options=[])
    )
    mock.get_active_program_options = AsyncMock(return_value=ArrayOfOptions([]))
    mock.get_selected_program_options = AsyncMock(return_value=ArrayOfOptions([]))
    mock.set_active_program_option = AsyncMock(
        side_effect=set_program_option_side_effect
    )
    mock.set_selected_program_option = AsyncMock(
        side_effect=set_program_option_side_effect
    )

    mock.side_effect = mock
    return mock


@pytest.fixture(name="client_with_exception")
def mock_client_with_exception(
    appliances: list[HomeAppliance],
    appliance: HomeAppliance | None,
    request: pytest.FixtureRequest,
) -> MagicMock:
    """Fixture to mock Client from HomeConnect that raise exceptions."""
    mock = MagicMock(
        autospec=HomeConnectClient,
    )

    exception = HomeConnectError()
    if hasattr(request, "param") and request.param:
        exception = request.param

    event_queue: asyncio.Queue[list[EventMessage]] = asyncio.Queue()

    async def stream_all_events() -> AsyncGenerator[EventMessage]:
        """Mock stream_all_events."""
        while True:
            for event in await event_queue.get():
                yield event

    appliances = [appliance] if appliance else appliances
    mock.get_home_appliances = AsyncMock(return_value=ArrayOfHomeAppliances(appliances))
    mock.stream_all_events = stream_all_events

    mock.start_program = AsyncMock(side_effect=exception)
    mock.stop_program = AsyncMock(side_effect=exception)
    mock.set_selected_program = AsyncMock(side_effect=exception)
    mock.stop_program = AsyncMock(side_effect=exception)
    mock.set_active_program_option = AsyncMock(side_effect=exception)
    mock.set_active_program_options = AsyncMock(side_effect=exception)
    mock.set_selected_program_option = AsyncMock(side_effect=exception)
    mock.set_selected_program_options = AsyncMock(side_effect=exception)
    mock.set_setting = AsyncMock(side_effect=exception)
    mock.get_settings = AsyncMock(side_effect=exception)
    mock.get_setting = AsyncMock(side_effect=exception)
    mock.get_status = AsyncMock(side_effect=exception)
    mock.get_all_programs = AsyncMock(side_effect=exception)
    mock.get_available_commands = AsyncMock(side_effect=exception)
    mock.put_command = AsyncMock(side_effect=exception)
    mock.get_available_program = AsyncMock(side_effect=exception)
    mock.get_active_program_options = AsyncMock(side_effect=exception)
    mock.get_selected_program_options = AsyncMock(side_effect=exception)
    mock.set_active_program_option = AsyncMock(side_effect=exception)
    mock.set_selected_program_option = AsyncMock(side_effect=exception)

    return mock


@pytest.fixture(name="appliances")
def mock_appliances(
    appliances_data: str, request: pytest.FixtureRequest
) -> list[HomeAppliance]:
    """Fixture to mock the returned appliances."""
    appliances = ArrayOfHomeAppliances.from_json(appliances_data).homeappliances
    appliance_types = {appliance.type for appliance in appliances}
    if hasattr(request, "param") and request.param:
        appliance_types = request.param
    return [appliance for appliance in appliances if appliance.type in appliance_types]


@pytest.fixture(name="appliance")
def mock_appliance(
    appliances_data: str, request: pytest.FixtureRequest
) -> HomeAppliance | None:
    """Fixture to mock a single specific appliance to return."""
    appliance_type = None
    if hasattr(request, "param") and request.param:
        appliance_type = request.param
    return next(
        (
            appliance
            for appliance in ArrayOfHomeAppliances.from_json(
                appliances_data
            ).homeappliances
            if appliance.type == appliance_type
        ),
        None,
    )


@pytest.fixture(name="appliances_data")
def appliances_data_fixture() -> str:
    """Fixture to return a the string for an array of appliances."""
    return load_fixture("appliances.json", integration=DOMAIN)
