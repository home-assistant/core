"""Configure py.test."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from vizaio import AppConfig, InputInfo, SettingInfo, SettingType, VizioConnectionError
from vizaio.profiles import SOUNDBAR_PROFILE

from homeassistant.components.vizio.const import DOMAIN
from homeassistant.core import HomeAssistant

from .const import (
    ACCESS_TOKEN,
    APP_RECORDS,
    CURRENT_APP_CONFIG_OBJ,
    CURRENT_EQ,
    CURRENT_INPUT,
    EQ_LIST,
    INPUT_LIST,
    INPUT_LIST_WITH_APPS,
    MOCK_CRAVE_CONFIG,
    MOCK_SPEAKER_CONFIG,
    MOCK_USER_VALID_TV_CONFIG,
    MODEL,
    PAIR_CHALLENGE,
    UNIQUE_ID,
    VERSION,
    ZEROCONF_HOST,
    audio_setting,
)

from tests.common import MockConfigEntry


def get_mock_inputs(input_list: list[str]) -> list[InputInfo]:
    """Return list of InputInfo for the given input names."""
    return [
        InputInfo(name=name, meta_name=name, is_current=False) for name in input_list
    ]


@pytest.fixture
def mock_tv_config_entry() -> MockConfigEntry:
    """Return a mock TV config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_USER_VALID_TV_CONFIG,
        unique_id=UNIQUE_ID,
    )


@pytest.fixture
def mock_speaker_config_entry() -> MockConfigEntry:
    """Return a mock speaker config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_SPEAKER_CONFIG,
        unique_id=UNIQUE_ID,
    )


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Add config entry to hass and set up the integration."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture(autouse=True)
def vizio_no_classification() -> Generator[None]:
    """Mock device-type classification as unavailable by default."""
    with patch(
        "homeassistant.components.vizio.async_classify_device",
        side_effect=VizioConnectionError("cannot connect"),
    ):
        yield


@pytest.fixture
def mock_crave_config_entry() -> MockConfigEntry:
    """Return a mock Crave speaker config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CRAVE_CONFIG,
        unique_id=UNIQUE_ID,
    )


@pytest.fixture(name="vizio_get_unique_id", autouse=True)
def vizio_get_unique_id_fixture() -> Generator[None]:
    """Mock get vizio unique ID."""
    with patch(
        "homeassistant.components.vizio.config_flow.Vizio.get_serial_number",
        AsyncMock(return_value=UNIQUE_ID),
    ):
        yield


@pytest.fixture(name="vizio_data_coordinator_update", autouse=True)
def vizio_data_coordinator_update_fixture() -> Generator[None]:
    """Mock get data coordinator update."""
    with (
        patch(
            "homeassistant.components.vizio.coordinator.fetch_remote_app_catalog",
            return_value=APP_RECORDS,
        ),
        patch(
            "homeassistant.components.vizio.coordinator.fetch_app_availability",
            return_value=(),
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def no_delay_secs() -> Generator[None]:
    """Patch default delay between remote command repeats to 0."""
    with patch(
        "homeassistant.components.vizio.remote.DEFAULT_DELAY_SECS",
        0,
    ):
        yield


@pytest.fixture(name="vizio_data_coordinator_update_failure")
def vizio_data_coordinator_update_failure_fixture() -> Generator[None]:
    """Mock get data coordinator update failure."""
    with (
        patch(
            "homeassistant.components.vizio.coordinator.fetch_remote_app_catalog",
            side_effect=VizioConnectionError("fetch failed"),
        ),
        patch(
            "homeassistant.components.vizio.coordinator.fetch_app_availability",
            return_value=(),
        ),
    ):
        yield


@pytest.fixture(name="vizio_no_unique_id")
def vizio_no_unique_id_fixture() -> Generator[None]:
    """Mock no vizio unique ID returrned."""
    with patch(
        "homeassistant.components.vizio.config_flow.Vizio.get_serial_number",
        side_effect=VizioConnectionError("cannot connect"),
    ):
        yield


@pytest.fixture(name="vizio_connect")
def vizio_connect_fixture() -> Generator[None]:
    """Mock valid vizio device and entry setup."""
    with (
        patch(
            "homeassistant.components.vizio.config_flow.Vizio.ping",
            AsyncMock(return_value=None),
        ),
        patch(
            "homeassistant.components.vizio.config_flow.Vizio.ping_auth",
            AsyncMock(return_value=None),
        ),
    ):
        yield


@pytest.fixture(name="vizio_complete_pairing")
def vizio_complete_pairing_fixture() -> Generator[None]:
    """Mock complete vizio pairing workflow."""
    with (
        patch(
            "homeassistant.components.vizio.config_flow.Vizio.begin_pair",
            return_value=PAIR_CHALLENGE,
        ),
        patch(
            "homeassistant.components.vizio.config_flow.Vizio.finish_pair",
            return_value=ACCESS_TOKEN,
        ),
    ):
        yield


@pytest.fixture(name="vizio_start_pairing_failure")
def vizio_start_pairing_failure_fixture() -> Generator[None]:
    """Mock vizio start pairing failure."""
    with patch(
        "homeassistant.components.vizio.config_flow.Vizio.begin_pair",
        side_effect=VizioConnectionError("cannot connect"),
    ):
        yield


@pytest.fixture(name="vizio_invalid_pin_failure")
def vizio_invalid_pin_failure_fixture() -> Generator[None]:
    """Mock vizio failure due to invalid pin."""
    with (
        patch(
            "homeassistant.components.vizio.config_flow.Vizio.begin_pair",
            return_value=PAIR_CHALLENGE,
        ),
        patch(
            "homeassistant.components.vizio.config_flow.Vizio.finish_pair",
            side_effect=VizioConnectionError("invalid pin"),
        ),
    ):
        yield


@pytest.fixture(name="vizio_bypass_setup")
def vizio_bypass_setup_fixture() -> Generator[None]:
    """Mock component setup."""
    with patch("homeassistant.components.vizio.async_setup_entry", return_value=True):
        yield


@pytest.fixture(name="vizio_bypass_update")
def vizio_bypass_update_fixture() -> Generator[None]:
    """Mock component update with minimal data."""
    with (
        patch(
            "homeassistant.components.vizio.Vizio.get_power_state",
            return_value=True,
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_settings",
            return_value=None,
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_current_input",
            return_value=None,
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_inputs",
            return_value=None,
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_current_app_config",
            return_value=None,
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_model_name",
            return_value=None,
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_version",
            return_value=None,
        ),
    ):
        yield


@pytest.fixture(name="vizio_guess_device_type")
def vizio_guess_device_type_fixture() -> Generator[None]:
    """Mock vizio device type probe to report a speaker."""
    with patch(
        "homeassistant.components.vizio.config_flow.async_is_tv",
        return_value=False,
    ):
        yield


@pytest.fixture(name="vizio_cant_connect")
def vizio_cant_connect_fixture() -> Generator[None]:
    """Mock vizio device can't connect with valid auth."""
    with (
        patch(
            "homeassistant.components.vizio.config_flow.Vizio.ping",
            side_effect=VizioConnectionError("cannot connect"),
        ),
        patch(
            "homeassistant.components.vizio.config_flow.Vizio.ping_auth",
            side_effect=VizioConnectionError("cannot connect"),
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_power_state",
            side_effect=VizioConnectionError("cannot connect"),
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_model_name",
            side_effect=VizioConnectionError("cannot connect"),
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_version",
            side_effect=VizioConnectionError("cannot connect"),
        ),
    ):
        yield


@pytest.fixture(name="vizio_update")
def vizio_update_fixture() -> Generator[None]:
    """Mock valid updates to vizio device."""
    with (
        patch(
            "homeassistant.components.vizio.Vizio.get_settings",
            return_value={
                "volume": audio_setting("volume", int(SOUNDBAR_PROFILE.max_volume / 2)),
                "eq": audio_setting("eq", CURRENT_EQ),
                "mute": audio_setting("mute", "Off"),
            },
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_setting",
            return_value=SettingInfo(
                setting_type="audio",
                name="eq",
                value=CURRENT_EQ,
                hashval=0,
                type=SettingType.LIST,
                options=tuple(EQ_LIST),
            ),
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_current_input",
            return_value=CURRENT_INPUT,
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_inputs",
            return_value=get_mock_inputs(INPUT_LIST),
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_power_state",
            return_value=True,
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_model_name",
            return_value=MODEL,
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_version",
            return_value=VERSION,
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_current_app_config",
            return_value=None,
        ),
    ):
        yield


@pytest.fixture(name="vizio_update_with_apps")
def vizio_update_with_apps_fixture(vizio_update: None) -> Generator[None]:
    """Mock valid updates to vizio device that supports apps."""
    with (
        patch(
            "homeassistant.components.vizio.Vizio.get_inputs",
            return_value=get_mock_inputs(INPUT_LIST_WITH_APPS),
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_current_input",
            return_value="CAST",
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_current_app_config",
            return_value=CURRENT_APP_CONFIG_OBJ,
        ),
    ):
        yield


@pytest.fixture(name="vizio_update_with_apps_on_input")
def vizio_update_with_apps_on_input_fixture(vizio_update: None) -> Generator[None]:
    """Mock valid updates to vizio device that supports apps but is on a TV input."""
    with (
        patch(
            "homeassistant.components.vizio.Vizio.get_inputs",
            return_value=get_mock_inputs(INPUT_LIST_WITH_APPS),
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_current_input",
            return_value=CURRENT_INPUT,
        ),
        patch(
            "homeassistant.components.vizio.Vizio.get_current_app_config",
            return_value=AppConfig(app_id="unknown", name_space=1, message="app"),
        ),
    ):
        yield


@pytest.fixture(name="vizio_hostname_check")
def vizio_hostname_check() -> Generator[None]:
    """Mock vizio hostname resolution."""
    with patch(
        "homeassistant.components.vizio.config_flow.socket.gethostbyname",
        return_value=ZEROCONF_HOST,
    ):
        yield
