"""Test Onkyo config flow."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.onkyo import InputSource
from homeassistant.components.onkyo.config_flow import OnkyoConfigFlow
from homeassistant.components.onkyo.const import (
    DOMAIN,
    OPTION_MAX_VOLUME,
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

from . import (
    create_config_entry_from_info,
    create_connection,
    create_empty_config_entry,
    create_receiver_info,
    setup_integration,
)

from tests.common import MockConfigEntry


async def test_user_initial_menu(hass: HomeAssistant) -> None:
    """Test initial menu."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert init_result["type"] is FlowResultType.MENU
    # Check if the values are there, but ignore order
    assert not set(init_result["menu_options"]) ^ {"manual", "eiscp_discovery"}


async def test_manual_valid_host(hass: HomeAssistant, default_mock_discovery) -> None:
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
        user_input={CONF_HOST: "host 1"},
    )

    assert select_result["step_id"] == "configure_receiver"
    assert select_result["description_placeholders"]["name"] == "type 1 (host 1)"


async def test_manual_invalid_host(hass: HomeAssistant, stub_mock_discovery) -> None:
    """Test invalid host entered."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    form_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {"next_step_id": "manual"},
    )

    host_result = await hass.config_entries.flow.async_configure(
        form_result["flow_id"],
        user_input={CONF_HOST: "sample-host-name"},
    )

    assert host_result["step_id"] == "manual"
    assert host_result["errors"]["base"] == "cannot_connect"


async def test_ssdp_discovery_already_configured(
    hass: HomeAssistant, default_mock_discovery
) -> None:
    """Test SSDP discovery with already configured device."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100"},
        unique_id="id1",
    )
    config_entry.add_to_hass(hass)

    discovery_info = SsdpServiceInfo(
        ssdp_location="http://192.168.1.100:8080",
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


async def test_manual_valid_host_unexpected_error(
    hass: HomeAssistant, empty_mock_discovery
) -> None:
    """Test valid host entered."""

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    form_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {"next_step_id": "manual"},
    )

    host_result = await hass.config_entries.flow.async_configure(
        form_result["flow_id"],
        user_input={CONF_HOST: "sample-host-name"},
    )

    assert host_result["step_id"] == "manual"
    assert host_result["errors"]["base"] == "unknown"


async def test_discovery_and_no_devices_discovered(
    hass: HomeAssistant, stub_mock_discovery
) -> None:
    """Test initial menu."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    form_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {"next_step_id": "eiscp_discovery"},
    )

    assert form_result["type"] is FlowResultType.ABORT
    assert form_result["reason"] == "no_devices_found"


async def test_discovery_with_exception(
    hass: HomeAssistant, empty_mock_discovery
) -> None:
    """Test discovery which throws an unexpected exception."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    form_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"],
        {"next_step_id": "eiscp_discovery"},
    )

    assert form_result["type"] is FlowResultType.ABORT
    assert form_result["reason"] == "unknown"


async def test_discovery_with_new_and_existing_found(hass: HomeAssistant) -> None:
    """Test discovery with a new and an existing entry."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    async def mock_discover(discovery_callback, timeout):
        await discovery_callback(create_connection(1))
        await discovery_callback(create_connection(2))

    with (
        patch("pyeiscp.Connection.discover", new=mock_discover),
        # Fake it like the first entry was already added
        patch.object(OnkyoConfigFlow, "_async_current_ids", return_value=["id1"]),
    ):
        form_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            {"next_step_id": "eiscp_discovery"},
        )

    assert form_result["type"] is FlowResultType.FORM

    assert form_result["data_schema"] is not None
    schema = form_result["data_schema"].schema
    container = schema["device"].container
    assert container == {"id2": "type 2 (host 2)"}


async def test_discovery_with_one_selected(hass: HomeAssistant) -> None:
    """Test discovery after a selection."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    async def mock_discover(discovery_callback, timeout):
        await discovery_callback(create_connection(42))
        await discovery_callback(create_connection(0))

    with patch("pyeiscp.Connection.discover", new=mock_discover):
        form_result = await hass.config_entries.flow.async_configure(
            init_result["flow_id"],
            {"next_step_id": "eiscp_discovery"},
        )

        select_result = await hass.config_entries.flow.async_configure(
            form_result["flow_id"],
            user_input={"device": "id42"},
        )

    assert select_result["step_id"] == "configure_receiver"
    assert select_result["description_placeholders"]["name"] == "type 42 (host 42)"


async def test_ssdp_discovery_success(
    hass: HomeAssistant, default_mock_discovery
) -> None:
    """Test SSDP discovery with valid host."""
    discovery_info = SsdpServiceInfo(
        ssdp_location="http://192.168.1.100:8080",
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

    select_result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"volume_resolution": 200, "input_sources": ["TV"]},
    )

    assert select_result["type"] is FlowResultType.CREATE_ENTRY
    assert select_result["data"]["host"] == "192.168.1.100"
    assert select_result["result"].unique_id == "id1"


async def test_ssdp_discovery_host_info_error(hass: HomeAssistant) -> None:
    """Test SSDP discovery with host info error."""
    discovery_info = SsdpServiceInfo(
        ssdp_location="http://192.168.1.100:8080",
        upnp={ATTR_UPNP_FRIENDLY_NAME: "Onkyo Receiver"},
        ssdp_usn="uuid:mock_usn",
        ssdp_st="mock_st",
    )

    with patch(
        "homeassistant.components.onkyo.receiver.pyeiscp.Connection.discover",
        side_effect=OSError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_SSDP},
            data=discovery_info,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_ssdp_discovery_host_none_info(
    hass: HomeAssistant, stub_mock_discovery
) -> None:
    """Test SSDP discovery with host info error."""
    discovery_info = SsdpServiceInfo(
        ssdp_location="http://192.168.1.100:8080",
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
    assert result["reason"] == "cannot_connect"


async def test_ssdp_discovery_no_location(
    hass: HomeAssistant, default_mock_discovery
) -> None:
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


async def test_ssdp_discovery_no_host(
    hass: HomeAssistant, default_mock_discovery
) -> None:
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


async def test_configure_empty_source_list(
    hass: HomeAssistant, default_mock_discovery
) -> None:
    """Test receiver configuration with no sources set."""

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

    configure_result = await hass.config_entries.flow.async_configure(
        select_result["flow_id"],
        user_input={"volume_resolution": 200, "input_sources": []},
    )

    assert configure_result["errors"] == {"input_sources": "empty_input_source_list"}


async def test_configure_no_resolution(
    hass: HomeAssistant, default_mock_discovery
) -> None:
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


async def test_configure_resolution_set(
    hass: HomeAssistant, default_mock_discovery
) -> None:
    """Test receiver configure with specified resolution."""

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

    configure_result = await hass.config_entries.flow.async_configure(
        select_result["flow_id"],
        user_input={"volume_resolution": 200, "input_sources": ["TV"]},
    )

    assert configure_result["type"] is FlowResultType.CREATE_ENTRY
    assert configure_result["options"]["volume_resolution"] == 200


async def test_configure_invalid_resolution_set(
    hass: HomeAssistant, default_mock_discovery
) -> None:
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


async def test_reconfigure(hass: HomeAssistant, default_mock_discovery) -> None:
    """Test the reconfigure config flow."""
    receiver_info = create_receiver_info(1)
    config_entry = create_config_entry_from_info(receiver_info)
    await setup_integration(hass, config_entry, receiver_info)

    old_host = config_entry.data[CONF_HOST]
    old_max_volume = config_entry.options[OPTION_MAX_VOLUME]

    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"host": receiver_info.host}
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "configure_receiver"

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={"volume_resolution": 200, "input_sources": ["TUNER"]},
    )

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reconfigure_successful"

    assert config_entry.data[CONF_HOST] == old_host
    assert config_entry.options[OPTION_VOLUME_RESOLUTION] == 200
    assert config_entry.options[OPTION_MAX_VOLUME] == old_max_volume


async def test_reconfigure_new_device(hass: HomeAssistant) -> None:
    """Test the reconfigure config flow with new device."""
    receiver_info = create_receiver_info(1)
    config_entry = create_config_entry_from_info(receiver_info)
    await setup_integration(hass, config_entry, receiver_info)

    old_unique_id = receiver_info.identifier

    result = await config_entry.start_reconfigure_flow(hass)

    mock_connection = create_connection(2)

    # Create mock discover that calls callback immediately
    async def mock_discover(host, discovery_callback, timeout):
        await discovery_callback(mock_connection)

    with patch(
        "homeassistant.components.onkyo.receiver.pyeiscp.Connection.discover",
        new=mock_discover,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"host": mock_connection.host}
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "unique_id_mismatch"

    # unique id should remain unchanged
    assert config_entry.unique_id == old_unique_id


@pytest.mark.parametrize(
    ("user_input", "exception", "error"),
    [
        (
            # No host, and thus no host reachable
            {
                CONF_HOST: None,
                "receiver_max_volume": 100,
                "max_volume": 100,
                "sources": {},
            },
            None,
            "cannot_connect",
        ),
        (
            # No host, and connection exception
            {
                CONF_HOST: None,
                "receiver_max_volume": 100,
                "max_volume": 100,
                "sources": {},
            },
            Exception(),
            "cannot_connect",
        ),
    ],
)
async def test_import_fail(
    hass: HomeAssistant,
    user_input: dict[str, Any],
    exception: Exception,
    error: str,
) -> None:
    """Test import flow failed."""

    with patch(
        "homeassistant.components.onkyo.receiver.pyeiscp.Connection.discover",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=user_input
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == error


async def test_import_success(
    hass: HomeAssistant,
) -> None:
    """Test import flow succeeded."""
    info = create_receiver_info(1)

    user_input = {
        CONF_HOST: info.host,
        "receiver_max_volume": 80,
        "max_volume": 110,
        "sources": {
            InputSource("00"): "Auxiliary",
            InputSource("01"): "Video",
        },
        "info": info,
    }

    import_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=user_input
    )
    await hass.async_block_till_done()

    assert import_result["type"] is FlowResultType.CREATE_ENTRY
    assert import_result["data"]["host"] == "host 1"
    assert import_result["options"]["volume_resolution"] == 80
    assert import_result["options"]["max_volume"] == 100
    assert import_result["options"]["input_sources"] == {
        "00": "Auxiliary",
        "01": "Video",
    }


@pytest.mark.parametrize(
    "ignore_translations",
    [
        [  # The schema is dynamically created from input sources
            "component.onkyo.options.step.init.data.TV",
            "component.onkyo.options.step.init.data_description.TV",
        ]
    ],
)
async def test_options_flow(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test options flow."""

    receiver_info = create_receiver_info(1)
    config_entry = create_empty_config_entry()
    await setup_integration(hass, config_entry, receiver_info)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "max_volume": 42,
            "TV": "television",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "volume_resolution": 80,
        "max_volume": 42.0,
        "input_sources": {
            "12": "television",
        },
    }
