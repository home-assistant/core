"""Test Onkyo config flow."""

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
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    SsdpServiceInfo,
)

from . import RECEIVER_INFO, RECEIVER_INFO_2, mock_discovery, setup_integration

from tests.common import MockConfigEntry


def _entry_title(receiver_info: ReceiverInfo) -> str:
    return f"{receiver_info.model_name} ({receiver_info.host})"


async def test_user_initial_menu(hass: HomeAssistant) -> None:
    """Test initial menu."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert init_result["type"] is FlowResultType.MENU
    # Check if the values are there, but ignore order
    assert not set(init_result["menu_options"]) ^ {"manual", "eiscp_discovery"}


async def test_manual_valid_host(hass: HomeAssistant) -> None:
    """Test valid host entered."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    form_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {"next_step_id": "manual"},
    )

    select_result = await hass.config_entries.flow.async_configure(
        form_result["flow_id"],
        user_input={CONF_HOST: RECEIVER_INFO.host},
    )

    assert select_result["step_id"] == "configure_receiver"
    assert select_result["description_placeholders"]["name"] == _entry_title(
        RECEIVER_INFO
    )


async def test_manual_invalid_host(hass: HomeAssistant) -> None:
    """Test invalid host entered."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    form_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {"next_step_id": "manual"},
    )

    with mock_discovery([]):
        host_result = await hass.config_entries.flow.async_configure(
            form_result["flow_id"],
            user_input={CONF_HOST: "sample-host-name"},
        )

    assert host_result["step_id"] == "manual"
    assert host_result["errors"]["base"] == "cannot_connect"


async def test_manual_valid_host_unexpected_error(hass: HomeAssistant) -> None:
    """Test valid host entered."""

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    form_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {"next_step_id": "manual"},
    )

    with mock_discovery(None):
        host_result = await hass.config_entries.flow.async_configure(
            form_result["flow_id"],
            user_input={CONF_HOST: "sample-host-name"},
        )

    assert host_result["step_id"] == "manual"
    assert host_result["errors"]["base"] == "unknown"


async def test_eiscp_discovery_no_devices_found(hass: HomeAssistant) -> None:
    """Test eiscp discovery with no devices found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with mock_discovery([]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "eiscp_discovery"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_eiscp_discovery_unexpected_exception(hass: HomeAssistant) -> None:
    """Test eiscp discovery with an unexpected exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with mock_discovery(None):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "eiscp_discovery"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_eiscp_discovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test eiscp discovery."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with mock_discovery([RECEIVER_INFO, RECEIVER_INFO_2]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"next_step_id": "eiscp_discovery"},
        )

    assert result["type"] is FlowResultType.FORM

    assert result["data_schema"] is not None
    schema = result["data_schema"].schema
    container = schema["device"].container
    assert container == {RECEIVER_INFO_2.identifier: _entry_title(RECEIVER_INFO_2)}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"device": RECEIVER_INFO_2.identifier},
    )

    assert result["step_id"] == "configure_receiver"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "volume_resolution": 200,
            "input_sources": ["TV"],
            "listening_modes": ["THX"],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["host"] == RECEIVER_INFO_2.host
    assert result["result"].unique_id == RECEIVER_INFO_2.identifier


@pytest.mark.usefixtures("mock_setup_entry")
async def test_ssdp_discovery_success(hass: HomeAssistant) -> None:
    """Test SSDP discovery with valid host."""
    discovery_info = SsdpServiceInfo(
        ssdp_location="http://192.168.0.101:8080",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "Onkyo Receiver"},
        ssdp_usn="uuid:mock_usn",
        ssdp_udn="uuid:00000000-0000-0000-0000-000000000000",
        ssdp_st="mock_st",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_receiver"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "volume_resolution": 200,
            "input_sources": ["TV"],
            "listening_modes": ["THX"],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["host"] == RECEIVER_INFO.host
    assert result["result"].unique_id == RECEIVER_INFO.identifier


async def test_ssdp_discovery_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test SSDP discovery with already configured device."""
    mock_config_entry.add_to_hass(hass)

    discovery_info = SsdpServiceInfo(
        ssdp_location="http://192.168.0.101:8080",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "Onkyo Receiver"},
        ssdp_usn="uuid:mock_usn",
        ssdp_udn="uuid:00000000-0000-0000-0000-000000000000",
        ssdp_st="mock_st",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_ssdp_discovery_host_info_error(hass: HomeAssistant) -> None:
    """Test SSDP discovery with host info error."""
    discovery_info = SsdpServiceInfo(
        ssdp_location="http://192.168.1.100:8080",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "Onkyo Receiver"},
        ssdp_usn="uuid:mock_usn",
        ssdp_st="mock_st",
    )

    with mock_discovery(None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=discovery_info,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_ssdp_discovery_host_none_info(hass: HomeAssistant) -> None:
    """Test SSDP discovery with host info error."""
    discovery_info = SsdpServiceInfo(
        ssdp_location="http://192.168.1.100:8080",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "Onkyo Receiver"},
        ssdp_usn="uuid:mock_usn",
        ssdp_st="mock_st",
    )

    with mock_discovery([]):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=discovery_info,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_ssdp_discovery_no_location(hass: HomeAssistant) -> None:
    """Test SSDP discovery with no location."""
    discovery_info = SsdpServiceInfo(
        ssdp_location=None,
        upnp={ATTR_UPNP_FRIENDLY_NAME: "Onkyo Receiver"},
        ssdp_usn="uuid:mock_usn",
        ssdp_st="mock_st",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_ssdp_discovery_no_host(hass: HomeAssistant) -> None:
    """Test SSDP discovery with no host."""
    discovery_info = SsdpServiceInfo(
        ssdp_location="http://",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "Onkyo Receiver"},
        ssdp_usn="uuid:mock_usn",
        ssdp_st="mock_st",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_configure_no_resolution(hass: HomeAssistant) -> None:
    """Test receiver configure with no resolution set."""

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    form_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {"next_step_id": "manual"},
    )

    select_result = await hass.config_entries.flow.async_configure(
        form_result["flow_id"],
        user_input={CONF_HOST: "sample-host-name"},
    )

    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            select_result["flow_id"],
            user_input={"input_sources": ["TV"]},
        )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_configure(hass: HomeAssistant) -> None:
    """Test receiver configure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": "manual"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: RECEIVER_INFO.host},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            OPTION_VOLUME_RESOLUTION: 200,
            OPTION_INPUT_SOURCES: [],
            OPTION_LISTENING_MODES: ["THX"],
        },
    )
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


async def test_configure_invalid_resolution_set(hass: HomeAssistant) -> None:
    """Test receiver configure with invalid resolution."""

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    form_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {"next_step_id": "manual"},
    )

    select_result = await hass.config_entries.flow.async_configure(
        form_result["flow_id"],
        user_input={CONF_HOST: "sample-host-name"},
    )

    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            select_result["flow_id"],
            user_input={"volume_resolution": 42, "input_sources": ["TV"]},
        )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the reconfigure config flow."""
    await setup_integration(hass, mock_config_entry)

    old_host = mock_config_entry.data[CONF_HOST]
    old_options = mock_config_entry.options

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"host": mock_config_entry.data[CONF_HOST]}
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "configure_receiver"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={OPTION_VOLUME_RESOLUTION: 200},
    )

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reconfigure_successful"

    assert mock_config_entry.data[CONF_HOST] == old_host
    assert mock_config_entry.options[OPTION_VOLUME_RESOLUTION] == 200
    for option, option_value in old_options.items():
        if option == OPTION_VOLUME_RESOLUTION:
            continue
        assert mock_config_entry.options[option] == option_value


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_new_device(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the reconfigure config flow with new device."""
    await setup_integration(hass, mock_config_entry)

    old_unique_id = mock_config_entry.unique_id

    result = await mock_config_entry.start_reconfigure_flow(hass)

    with mock_discovery([RECEIVER_INFO_2]):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: RECEIVER_INFO_2.host}
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "unique_id_mismatch"

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
