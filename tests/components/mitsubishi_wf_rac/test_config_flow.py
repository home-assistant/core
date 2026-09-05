"""Test the Mitsubishi WF-RAC config flow."""

from unittest.mock import AsyncMock

import pytest
from pywfrac import WfRacConnectionError

from homeassistant.components.mitsubishi_wf_rac.config_flow import WfRacConfigFlow
from homeassistant.components.mitsubishi_wf_rac.const import (
    CONF_AIRCO_ID,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import AIRCO_ID, HOST, PORT

from tests.common import MockConfigEntry

USER_INPUT = {CONF_NAME: "Living room", CONF_HOST: HOST, CONF_PORT: PORT}


def _discovery_info(port: int = PORT) -> ZeroconfServiceInfo:
    return ZeroconfServiceInfo(
        ip_address=HOST,
        ip_addresses=[HOST],
        hostname=f"{AIRCO_ID}.local.",
        name=f"{AIRCO_ID}._beaver._tcp.local.",
        port=port,
        type="_beaver._tcp.local.",
        properties={},
    )


async def test_user_flow(
    hass: HomeAssistant, mock_repository: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """A manually added airco is queried, registered and stored."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living room"
    assert result["data"][CONF_AIRCO_ID] == AIRCO_ID
    assert result["options"][CONF_HOST] == HOST
    mock_repository.update_account_info.assert_awaited_once()


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (WfRacConnectionError("no route"), "cannot_connect"),
        (KeyError("airconId"), "cannot_connect"),
    ],
)
async def test_user_flow_connection_errors(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    error: str,
) -> None:
    """An unreachable airco shows the form again, then recovers."""
    mock_repository.get_airco_id.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == error

    mock_repository.get_airco_id.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_empty_airco_id(
    hass: HomeAssistant, mock_repository: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """A module that answers without an airconId is not usable."""
    mock_repository.get_airco_id.return_value = ""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_user_flow_account_table_full(
    hass: HomeAssistant, mock_repository: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """result:2 from updateAccountInfo means no slot is free."""
    mock_repository.update_account_info.return_value = {"result": 2}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "too_many_devices_registered"


async def test_user_flow_registration_refused(
    hass: HomeAssistant, mock_repository: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """An empty registration response is treated as a failed connection."""
    mock_repository.update_account_info.return_value = {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        (CONF_HOST, "ab", "invalid_host"),
        (CONF_NAME, "ab", "name_invalid"),
    ],
)
async def test_user_flow_input_validation(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    mock_setup_entry: AsyncMock,
    field: str,
    value: str,
    error: str,
) -> None:
    """Host and name are checked before the airco is contacted.

    Both errors land on their own field rather than on the form as a whole.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, field: value}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"][field] == error


async def test_user_flow_duplicate_host(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A second entry on the same address is refused unless forced."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"][CONF_HOST] == "host_already_configured"


async def test_zeroconf_flow(
    hass: HomeAssistant, mock_repository: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """A discovered airco only needs a name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery_info()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: "Living room", CONF_PORT: PORT}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_AIRCO_ID] == AIRCO_ID


async def test_zeroconf_flow_port_fallback(
    hass: HomeAssistant, mock_repository: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """An announced port the module does not serve falls back to 51443.

    Only the announced value is second-guessed; the entry is stored with the
    port that actually answered.
    """
    mock_repository.get_airco_id.side_effect = [WfRacConnectionError("x"), AIRCO_ID]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery_info(port=5353)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: "Living room", CONF_PORT: 5353}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PORT] == DEFAULT_PORT


async def test_zeroconf_flow_already_configured(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A rediscovered airco aborts and refreshes the stored address."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery_info()
    )

    assert result["type"] is FlowResultType.ABORT


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Reconfigure validates the new address against the airco."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "Living room", CONF_HOST: "192.168.1.9", CONF_PORT: PORT},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.options[CONF_HOST] == "192.168.1.9"


async def test_options_flow(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Offsets round-trip, and options the form did not show survive."""
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "availability_retry_limit": 5,
            "setpoint_offsets": {"target_offset": 1.0},
            "sensor_offsets": {"indoor_offset": -0.5, "outdoor_offset": 0.0},
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    options = init_integration.options
    assert options["availability_retry_limit"] == 5
    assert options["target_offset"] == 1.0
    assert options["indoor_offset"] == -0.5
    # Never collected by this form, and it must not be dropped by saving it.
    assert options[CONF_HOST] == HOST


async def test_zeroconf_flow_port_fallback_also_fails(
    hass: HomeAssistant, mock_repository: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """When 51443 does not answer either, the fallback stops guessing."""
    mock_repository.get_airco_id.side_effect = WfRacConnectionError("no route")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery_info(port=5353)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: "Living room", CONF_PORT: 5353}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.parametrize("source", [SOURCE_USER, SOURCE_ZEROCONF])
async def test_unexpected_error_is_shown_not_raised(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    mock_setup_entry: AsyncMock,
    source: str,
) -> None:
    """A bug behind the form must not take the whole flow down."""
    mock_repository.get_airco_id.side_effect = RuntimeError("boom")

    if source == SOURCE_USER:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}
        )
        user_input = USER_INPUT
    else:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=_discovery_info()
        )
        user_input = {CONF_NAME: "Living room", CONF_PORT: PORT}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unexpected_error"


async def test_reconfigure_unexpected_error(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Same for the reconfigure step, which has its own boundary."""
    mock_config_entry.add_to_hass(hass)
    mock_repository.get_airco_id.side_effect = RuntimeError("boom")

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "Living room", CONF_HOST: "192.168.1.9", CONF_PORT: PORT},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unexpected_error"


async def test_reconfigure_known_error(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A reachable-but-refusing airco keeps the reconfigure form open."""
    mock_config_entry.add_to_hass(hass)
    mock_repository.update_account_info.return_value = {"result": 2}

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "Living room", CONF_HOST: "192.168.1.9", CONF_PORT: PORT},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "too_many_devices_registered"


async def test_two_discovery_flows_for_one_airco_match(
    hass: HomeAssistant, mock_repository: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """A second announcement joins the flow already in progress."""
    first = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery_info()
    )
    assert first["type"] is FlowResultType.FORM

    second = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery_info()
    )

    assert second["type"] is FlowResultType.ABORT
    assert second["reason"] == "already_in_progress"


async def test_zeroconf_flow_host_taken_by_another_airco(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A new airco announcing an address another entry already uses aborts.

    Two entries polling one address is the failure the manual flow's
    duplicate-IP switch exists to override; discovery does not offer that.
    """
    mock_config_entry.add_to_hass(hass)

    discovery = _discovery_info()
    other = ZeroconfServiceInfo(
        ip_address=discovery.ip_address,
        ip_addresses=discovery.ip_addresses,
        hostname="bbccddee1122.local.",
        name="bbccddee1122._beaver._tcp.local.",
        port=PORT,
        type="_beaver._tcp.local.",
        properties={},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=other
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_is_matching_compares_unique_ids(hass: HomeAssistant) -> None:
    """Discovery dedup rests on the airco id, and refuses to guess without it."""
    flow = WfRacConfigFlow()
    other = WfRacConfigFlow()

    flow.context = {"unique_id": AIRCO_ID}
    other.context = {"unique_id": AIRCO_ID}
    assert flow.is_matching(other) is True

    other.context = {"unique_id": "bbccddee1122"}
    assert flow.is_matching(other) is False

    other.context = {}
    assert flow.is_matching(other) is False
