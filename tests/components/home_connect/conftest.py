"""Test fixtures for home_connect."""

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
import copy
import time
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

from aiohomeconnect.client import Client as HomeConnectClient
from aiohomeconnect.model import (
    ArrayOfEvents,
    ArrayOfHomeAppliances,
    ArrayOfOptions,
    ArrayOfPrograms,
    ArrayOfSettings,
    ArrayOfStatus,
    Event,
    EventKey,
    EventMessage,
    EventType,
    GetSetting,
    HomeAppliance,
    Option,
    Program,
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

from tests.common import MockConfigEntry, load_json_object_fixture

MOCK_APPLIANCES = ArrayOfHomeAppliances.from_dict(
    load_json_object_fixture("home_connect/appliances.json")["data"]
)
MOCK_PROGRAMS: dict[str, Any] = load_json_object_fixture("home_connect/programs.json")
MOCK_SETTINGS: dict[str, Any] = load_json_object_fixture("home_connect/settings.json")
MOCK_STATUS = ArrayOfStatus.from_dict(
    load_json_object_fixture("home_connect/status.json")["data"]
)


CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
FAKE_ACCESS_TOKEN = "some-access-token"
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
        minor_version=2,
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


def _get_specific_appliance_side_effect(ha_id: str) -> HomeAppliance:
    """Get specific appliance side effect."""
    for appliance in copy.deepcopy(MOCK_APPLIANCES).homeappliances:
        if appliance.ha_id == ha_id:
            return appliance
    raise HomeConnectApiError("error.key", "error description")


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


async def _get_all_programs_side_effect(ha_id: str) -> ArrayOfPrograms:
    """Get all programs."""
    appliance_type = next(
        appliance
        for appliance in MOCK_APPLIANCES.homeappliances
        if appliance.ha_id == ha_id
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
                appliance
                for appliance in MOCK_APPLIANCES.homeappliances
                if appliance.ha_id == ha_id
            ).type,
            {},
        ).get("data", {"settings": []})
    )


async def _get_setting_side_effect(ha_id: str, setting_key: SettingKey):
    """Get setting."""
    for appliance in MOCK_APPLIANCES.homeappliances:
        if appliance.ha_id == ha_id:
            settings = MOCK_SETTINGS.get(
                next(
                    appliance
                    for appliance in MOCK_APPLIANCES.homeappliances
                    if appliance.ha_id == ha_id
                ).type,
                {},
            ).get("data", {"settings": []})
            for setting_dict in cast(list[dict], settings["settings"]):
                if setting_dict["key"] == setting_key:
                    return GetSetting.from_dict(setting_dict)
    raise HomeConnectApiError("error.key", "error description")


@pytest.fixture(name="client")
def mock_client(request: pytest.FixtureRequest) -> MagicMock:
    """Fixture to mock Client from HomeConnect."""

    mock = MagicMock(
        autospec=HomeConnectClient,
    )

    event_queue: asyncio.Queue[list[EventMessage]] = asyncio.Queue()

    async def add_events(events: list[EventMessage]) -> None:
        await event_queue.put(events)

    mock.add_events = add_events

    async def stream_all_events() -> AsyncGenerator[EventMessage]:
        """Mock stream_all_events."""
        while True:
            for event in await event_queue.get():
                yield event

    mock.get_home_appliances = AsyncMock(return_value=copy.deepcopy(MOCK_APPLIANCES))
    mock.get_specific_appliance = AsyncMock(
        side_effect=_get_specific_appliance_side_effect
    )
    mock.stream_all_events = stream_all_events
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
    mock.put_command = AsyncMock()

    mock.side_effect = mock
    return mock


@pytest.fixture(name="client_with_exception")
def mock_client_with_exception(request: pytest.FixtureRequest) -> MagicMock:
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

    mock.get_home_appliances = AsyncMock(return_value=copy.deepcopy(MOCK_APPLIANCES))
    mock.stream_all_events = stream_all_events

    mock.start_program = AsyncMock(side_effect=exception)
    mock.stop_program = AsyncMock(side_effect=exception)
    mock.set_selected_program = AsyncMock(side_effect=exception)
    mock.set_active_program_option = AsyncMock(side_effect=exception)
    mock.set_active_program_options = AsyncMock(side_effect=exception)
    mock.set_selected_program_option = AsyncMock(side_effect=exception)
    mock.set_selected_program_options = AsyncMock(side_effect=exception)
    mock.set_setting = AsyncMock(side_effect=exception)
    mock.get_settings = AsyncMock(side_effect=exception)
    mock.get_setting = AsyncMock(side_effect=exception)
    mock.get_status = AsyncMock(side_effect=exception)
    mock.get_all_programs = AsyncMock(side_effect=exception)
    mock.put_command = AsyncMock(side_effect=exception)

    return mock


@pytest.fixture(name="appliance_ha_id")
def mock_appliance_ha_id(request: pytest.FixtureRequest) -> str:
    """Fixture to mock Appliance."""
    app = "Washer"
    if hasattr(request, "param") and request.param:
        app = request.param
    for appliance in MOCK_APPLIANCES.homeappliances:
        if appliance.type == app:
            return appliance.ha_id
    raise ValueError(f"Appliance {app} not found")
