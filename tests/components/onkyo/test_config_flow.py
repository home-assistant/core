"""Test Onkyo config flow."""

from contextlib import AbstractContextManager, nullcontext

from aioonkyo import ReceiverInfo
import pytest

from homeassistant import config_entries
from homeassistant.components.onkyo.const import (
    DOMAIN,
    OPTION_INPUT_SOURCES,
    OPTION_LISTENING_MODES,
    OPTION_MAX_VOLUME,
    OPTION_MAX_VOLUME_DEFAULT,
    OPTION_VOLUME_RESOLUTION,
)
from homeassistant.config_entries import SOURCE_IGNORE, SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    SsdpServiceInfo,
)

from . import RECEIVER_INFO, RECEIVER_INFO_2, mock_discovery, setup_integration

from tests.common import MockConfigEntry


def _receiver_display_name(receiver_info: ReceiverInfo) -> str:
    return f"{receiver_info.model_name} ({receiver_info.host})"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_manual(hass: HomeAssistant) -> None:
    """Test successful manual."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: RECEIVER_INFO_2.host}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_receiver"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            OPTION_VOLUME_RESOLUTION: 200,
            OPTION_INPUT_SOURCES: ["TV"],
            OPTION_LISTENING_MODES: ["THX"],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == RECEIVER_INFO_2.host
    assert result["result"].unique_id == RECEIVER_INFO_2.identifier
    assert result["title"] == RECEIVER_INFO_2.model_name


@pytest.mark.parametrize(
    ("mock_discovery", "error_reason"),
    [
        (mock_discovery(None), "unknown"),
        (mock_discovery([]), "cannot_connect"),
        (mock_discovery([RECEIVER_INFO]), "cannot_connect"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_manual_recoverable_error(
    hass: HomeAssistant, mock_discovery: AbstractContextManager, error_reason: str
) -> None:
    """Test manual with a recoverable error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    with mock_discovery:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: RECEIVER_INFO_2.host}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {"base": error_reason}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: RECEIVER_INFO_2.host}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_receiver"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            OPTION_VOLUME_RESOLUTION: 200,
            OPTION_INPUT_SOURCES: ["TV"],
            OPTION_LISTENING_MODES: ["THX"],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == RECEIVER_INFO_2.host
    assert result["result"].unique_id == RECEIVER_INFO_2.identifier
    assert result["title"] == RECEIVER_INFO_2.model_name


@pytest.mark.usefixtures("mock_setup_entry")
async def test_manual_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test manual with an error."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: RECEIVER_INFO.host}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_eiscp_discovery(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful eiscp discovery."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "eiscp_discovery"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "eiscp_discovery"

    devices = result["data_schema"].schema["device"].container
    assert devices == {
        RECEIVER_INFO_2.identifier: _receiver_display_name(RECEIVER_INFO_2)
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"device": RECEIVER_INFO_2.identifier}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_receiver"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            OPTION_VOLUME_RESOLUTION: 200,
            OPTION_INPUT_SOURCES: ["TV"],
            OPTION_LISTENING_MODES: ["THX"],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == RECEIVER_INFO_2.host
    assert result["result"].unique_id == RECEIVER_INFO_2.identifier
    assert result["title"] == RECEIVER_INFO_2.model_name


@pytest.mark.parametrize(
    ("mock_discovery", "error_reason"),
    [
        (mock_discovery(None), "unknown"),
        (mock_discovery([]), "no_devices_found"),
        (mock_discovery([RECEIVER_INFO]), "no_devices_found"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_eiscp_discovery_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: AbstractContextManager,
    error_reason: str,
) -> None:
    """Test eiscp discovery with an error."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    with mock_discovery:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "eiscp_discovery"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == error_reason


async def test_eiscp_discovery_replace_ignored_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test eiscp discovery can replace an ignored config entry."""
    mock_config_entry.source = SOURCE_IGNORE
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "eiscp_discovery"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "eiscp_discovery"

    devices = result["data_schema"].schema["device"].container
    assert devices == {
        RECEIVER_INFO.identifier: _receiver_display_name(RECEIVER_INFO),
        RECEIVER_INFO_2.identifier: _receiver_display_name(RECEIVER_INFO_2),
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"device": RECEIVER_INFO.identifier}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_receiver"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            OPTION_VOLUME_RESOLUTION: 200,
            OPTION_INPUT_SOURCES: ["TV"],
            OPTION_LISTENING_MODES: ["THX"],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == RECEIVER_INFO.host
    assert result["result"].unique_id == RECEIVER_INFO.identifier
    assert result["title"] == RECEIVER_INFO.model_name

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_ssdp_discovery(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful SSDP discovery."""
    await setup_integration(hass, mock_config_entry)

    discovery_info = SsdpServiceInfo(
        ssdp_location=f"http://{RECEIVER_INFO_2.host}:8080",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "Onkyo Receiver"},
        ssdp_usn="uuid:mock_usn",
        ssdp_udn="uuid:00000000-0000-0000-0000-000000000000",
        ssdp_st="mock_st",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=discovery_info
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_receiver"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            OPTION_VOLUME_RESOLUTION: 200,
            OPTION_INPUT_SOURCES: ["TV"],
            OPTION_LISTENING_MODES: ["THX"],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == RECEIVER_INFO_2.host
    assert result["result"].unique_id == RECEIVER_INFO_2.identifier
    assert result["title"] == RECEIVER_INFO_2.model_name


@pytest.mark.parametrize(
    ("ssdp_location", "mock_discovery", "error_reason"),
    [
        (None, nullcontext(), "unknown"),
        ("http://", nullcontext(), "unknown"),
        (f"http://{RECEIVER_INFO_2.host}:8080", mock_discovery(None), "unknown"),
        (f"http://{RECEIVER_INFO_2.host}:8080", mock_discovery([]), "cannot_connect"),
        (
            f"http://{RECEIVER_INFO_2.host}:8080",
            mock_discovery([RECEIVER_INFO]),
            "cannot_connect",
        ),
        (f"http://{RECEIVER_INFO.host}:8080", nullcontext(), "already_configured"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_ssdp_discovery_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    ssdp_location: str | None,
    mock_discovery: AbstractContextManager,
    error_reason: str,
) -> None:
    """Test SSDP discovery with an error."""
    await setup_integration(hass, mock_config_entry)

    discovery_info = SsdpServiceInfo(
        ssdp_location=ssdp_location,
        upnp={ATTR_UPNP_FRIENDLY_NAME: "Onkyo Receiver"},
        ssdp_usn="uuid:mock_usn",
        ssdp_udn="uuid:00000000-0000-0000-0000-000000000000",
        ssdp_st="mock_st",
    )

    with mock_discovery:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_SSDP}, data=discovery_info
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == error_reason


@pytest.mark.usefixtures("mock_setup_entry")
async def test_configure(hass: HomeAssistant) -> None:
    """Test receiver configure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: RECEIVER_INFO.host}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_receiver"
    assert result["description_placeholders"]["name"] == _receiver_display_name(
        RECEIVER_INFO
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            OPTION_VOLUME_RESOLUTION: 200,
            OPTION_INPUT_SOURCES: [],
            OPTION_LISTENING_MODES: ["THX"],
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_receiver"
    assert result["errors"] == {OPTION_INPUT_SOURCES: "empty_input_source_list"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            OPTION_VOLUME_RESOLUTION: 200,
            OPTION_INPUT_SOURCES: ["TV"],
            OPTION_LISTENING_MODES: [],
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_receiver"
    assert result["errors"] == {OPTION_LISTENING_MODES: "empty_listening_mode_list"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            OPTION_VOLUME_RESOLUTION: 200,
            OPTION_INPUT_SOURCES: ["TV"],
            OPTION_LISTENING_MODES: ["THX"],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {
        OPTION_VOLUME_RESOLUTION: 200,
        OPTION_MAX_VOLUME: OPTION_MAX_VOLUME_DEFAULT,
        OPTION_INPUT_SOURCES: {"12": "TV"},
        OPTION_LISTENING_MODES: {"04": "THX"},
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful reconfigure flow."""
    await setup_integration(hass, mock_config_entry)

    old_host = mock_config_entry.data[CONF_HOST]
    old_options = mock_config_entry.options

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: mock_config_entry.data[CONF_HOST]}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_receiver"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={OPTION_VOLUME_RESOLUTION: 200}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    assert mock_config_entry.data[CONF_HOST] == old_host
    assert mock_config_entry.options[OPTION_VOLUME_RESOLUTION] == 200
    for option, option_value in old_options.items():
        if option == OPTION_VOLUME_RESOLUTION:
            continue
        assert mock_config_entry.options[option] == option_value


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure flow with an error."""
    await setup_integration(hass, mock_config_entry)

    old_unique_id = mock_config_entry.unique_id

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: RECEIVER_INFO_2.host}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"

    # unique id should remain unchanged
    assert mock_config_entry.unique_id == old_unique_id


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    "ignore_missing_translations",
    [
        [  # The schema is dynamically created from input sources and listening modes
            "component.onkyo.options.step.names.sections.input_sources.data.TV",
            "component.onkyo.options.step.names.sections.input_sources.data_description.TV",
            "component.onkyo.options.step.names.sections.listening_modes.data.STEREO",
            "component.onkyo.options.step.names.sections.listening_modes.data_description.STEREO",
        ]
    ],
)
async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test options flow."""
    await setup_integration(hass, mock_config_entry)

    old_volume_resolution = mock_config_entry.options[OPTION_VOLUME_RESOLUTION]

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            OPTION_MAX_VOLUME: 42,
            OPTION_INPUT_SOURCES: [],
            OPTION_LISTENING_MODES: ["STEREO"],
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {OPTION_INPUT_SOURCES: "empty_input_source_list"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            OPTION_MAX_VOLUME: 42,
            OPTION_INPUT_SOURCES: ["TV"],
            OPTION_LISTENING_MODES: [],
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {OPTION_LISTENING_MODES: "empty_listening_mode_list"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            OPTION_MAX_VOLUME: 42,
            OPTION_INPUT_SOURCES: ["TV"],
            OPTION_LISTENING_MODES: ["STEREO"],
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "names"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            OPTION_INPUT_SOURCES: {"TV": "television"},
            OPTION_LISTENING_MODES: {"STEREO": "Duophonia"},
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        OPTION_VOLUME_RESOLUTION: old_volume_resolution,
        OPTION_MAX_VOLUME: 42.0,
        OPTION_INPUT_SOURCES: {"12": "television"},
        OPTION_LISTENING_MODES: {"00": "Duophonia"},
    }
