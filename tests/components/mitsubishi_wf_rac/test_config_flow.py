"""Test the Mitsubishi WF-RAC config flow."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from pywfrac import (
    WfRacAccountTableFullError,
    WfRacCommandError,
    WfRacConnectionError,
    WfRacMalformedResponseError,
)

from homeassistant.components.mitsubishi_wf_rac.const import (
    CONF_AIRCO_ID,
    CONF_OPERATOR_ID,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.setup import async_setup_component

from . import AIRCO_ID, ENTRY_DATA, HOST, PORT

from tests.common import MockConfigEntry

USER_INPUT = {CONF_HOST: HOST, CONF_PORT: PORT}


def _discovery_info(
    port: int | None = PORT,
    host: str = HOST,
    airco_id: str = AIRCO_ID,
    local_suffix: str = ".local",
) -> ZeroconfServiceInfo:
    return ZeroconfServiceInfo(
        ip_address=host,
        ip_addresses=[host],
        hostname=f"{airco_id}{local_suffix}.",
        name=f"{airco_id}._beaver._tcp.local.",
        port=port,
        type="_beaver._tcp.local.",
        properties={},
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow(hass: HomeAssistant, mock_repository: MagicMock) -> None:
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
    assert result["result"].unique_id == AIRCO_ID
    # The last four characters of the airco id tell units apart.
    assert result["title"] == f"WF-RAC {AIRCO_ID[-4:]}"
    assert AIRCO_ID not in result["title"]
    assert CONF_NAME not in result["data"]
    assert result["data"][CONF_AIRCO_ID] == AIRCO_ID
    assert result["data"][CONF_HOST] == HOST
    mock_repository.async_register.assert_awaited_once()


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(WfRacConnectionError("no route"), "cannot_connect", id="no_route"),
        pytest.param(KeyError("airconId"), "cannot_connect", id="malformed"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_connection_errors(
    hass: HomeAssistant, mock_repository: MagicMock, side_effect: Exception, error: str
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


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_empty_airco_id(
    hass: HomeAssistant, mock_repository: MagicMock
) -> None:
    """A module that answers without an airconId is not usable, until it names one."""
    mock_repository.get_airco_id.return_value = ""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"

    mock_repository.get_airco_id.return_value = AIRCO_ID
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_account_table_full(
    hass: HomeAssistant, mock_repository: MagicMock
) -> None:
    """A full account table gets its own error, and the form can be resubmitted."""
    mock_repository.async_register.side_effect = WfRacAccountTableFullError("full")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "too_many_devices_registered"

    mock_repository.async_register.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == AIRCO_ID


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(WfRacCommandError("refused"), id="refused"),
        pytest.param(WfRacMalformedResponseError("garbled"), id="garbled_answer"),
        pytest.param(WfRacConnectionError("gone"), id="unit_went_away"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_a_registration_that_fails_says_so(
    hass: HomeAssistant, mock_repository: MagicMock, error: Exception
) -> None:
    """A failed registration shows an error instead of storing an entry."""
    mock_repository.async_register.side_effect = error

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"

    mock_repository.async_register.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == AIRCO_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_duplicate_host(
    hass: HomeAssistant,
    mock_repository: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A second entry on the same address is refused before anything is registered."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_repository.get_airco_id.assert_not_awaited()
    mock_repository.async_register.assert_not_awaited()


@pytest.mark.usefixtures("mock_repository", "mock_setup_entry")
async def test_zeroconf_flow(hass: HomeAssistant) -> None:
    """A discovered airco only needs its announced port confirmed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery_info()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: PORT}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == AIRCO_ID
    assert result["data"][CONF_AIRCO_ID] == AIRCO_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow_port_fallback(
    hass: HomeAssistant, mock_repository: MagicMock
) -> None:
    """An announced port the module does not serve falls back to 51443."""
    mock_repository.get_airco_id.side_effect = [WfRacConnectionError("x"), AIRCO_ID]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery_info(port=5353)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: 5353}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PORT] == DEFAULT_PORT


@pytest.mark.usefixtures("mock_setup_entry")
async def test_a_port_corrected_in_the_form_is_not_second_guessed(
    hass: HomeAssistant, mock_repository: MagicMock
) -> None:
    """A port edited in the form is not retried on 51443."""
    mock_repository.get_airco_id.side_effect = WfRacConnectionError("x")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery_info(port=5353)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: 8080}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"
    assert mock_repository.get_airco_id.await_count == 1

    mock_repository.get_airco_id.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: 8080}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    # Still the port they typed.
    assert result["data"][CONF_PORT] == 8080


@pytest.mark.usefixtures("mock_setup_entry")
async def test_the_form_suggests_the_port_that_answered(
    hass: HomeAssistant, mock_repository: MagicMock
) -> None:
    """After a fallback, the re-shown form suggests the port that answered."""
    mock_repository.get_airco_id.side_effect = [
        WfRacConnectionError("x"),
        AIRCO_ID,
        AIRCO_ID,
    ]
    mock_repository.async_register.side_effect = WfRacAccountTableFullError("full")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery_info(port=5353)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: 5353}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "too_many_devices_registered"
    suggested = {
        key.schema: key.description["suggested_value"]
        for key in result["data_schema"].schema
    }
    assert suggested[CONF_PORT] == DEFAULT_PORT

    # The schema default must be the port that answered.
    mock_repository.async_register.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PORT] == DEFAULT_PORT
    # The dead port is not tried again on the second submission.
    assert mock_repository.get_airco_id.await_count == 3


@pytest.mark.usefixtures("mock_repository", "mock_setup_entry")
async def test_an_announcement_without_a_port_offers_the_fixed_one(
    hass: HomeAssistant,
) -> None:
    """A missing announced port defaults to the fixed one."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery_info(port=None)
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == AIRCO_ID
    assert result["data"][CONF_PORT] == DEFAULT_PORT


@pytest.mark.usefixtures("mock_repository", "mock_setup_entry")
async def test_zeroconf_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A rediscovered airco aborts and refreshes only the stored address."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_discovery_info(port=5353, host="192.168.1.9"),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.9"
    assert mock_config_entry.data[CONF_PORT] == PORT


@pytest.mark.usefixtures("mock_repository", "mock_setup_entry")
async def test_a_shouted_hostname_still_matches_the_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The unique id is compared in one case, whoever supplied it."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_discovery_info(host="192.168.1.9", airco_id=AIRCO_ID.upper()),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.9"


@pytest.mark.usefixtures("mock_repository", "mock_setup_entry")
async def test_a_shouted_local_suffix_is_still_the_suffix(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A suffix announced as .LOCAL. is still stripped."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_discovery_info(host="192.168.1.9", local_suffix=".LOCAL"),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.9"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_zeroconf_flow_port_fallback_also_fails(
    hass: HomeAssistant, mock_repository: MagicMock
) -> None:
    """When 51443 does not answer either, the fallback stops guessing."""
    mock_repository.get_airco_id.side_effect = WfRacConnectionError("no route")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery_info(port=5353)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: 5353}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"

    # The announced port is still tried first.
    mock_repository.get_airco_id.side_effect = [WfRacConnectionError("x"), AIRCO_ID]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: 5353}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PORT] == DEFAULT_PORT


@pytest.mark.parametrize(
    ("source", "discovery", "user_input"),
    [
        pytest.param(SOURCE_USER, None, USER_INPUT, id="manual"),
        pytest.param(
            SOURCE_ZEROCONF,
            _discovery_info(),
            {CONF_PORT: PORT},
            id="discovered",
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_unexpected_error_is_shown_not_raised(
    hass: HomeAssistant,
    mock_repository: MagicMock,
    source: str,
    discovery: ZeroconfServiceInfo | None,
    user_input: dict[str, Any],
) -> None:
    """A bug behind the form must not take the whole flow down."""
    mock_repository.get_airco_id.side_effect = RuntimeError("boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source}, data=discovery
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"

    mock_repository.get_airco_id.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_repository", "mock_setup_entry")
async def test_two_discovery_flows_for_one_airco_match(hass: HomeAssistant) -> None:
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


@pytest.mark.usefixtures("mock_repository", "mock_setup_entry")
async def test_zeroconf_flow_host_taken_by_another_airco(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A new airco announcing an address another entry uses aborts."""
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


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_refuses_a_unit_that_is_already_configured(
    hass: HomeAssistant, mock_repository: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """One unit reached at a second address is matched by its airco id."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_HOST: "192.168.1.9"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # Account slots are never freed, so the abort must precede the registration.
    mock_repository.async_register.assert_not_awaited()


@pytest.mark.usefixtures("mock_setup_entry")
async def test_a_second_flow_for_one_airco_registers_nothing(
    hass: HomeAssistant, mock_repository: MagicMock
) -> None:
    """Two flows for one unit abort before the second takes an account slot."""
    # The abort text comes from the homeassistant integration.
    assert await async_setup_component(hass, "homeassistant", {})

    discovery = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery_info()
    )
    assert discovery["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"
    mock_repository.async_register.assert_not_awaited()


@pytest.mark.usefixtures("mock_repository", "mock_setup_entry")
async def test_the_port_can_be_cleared_and_falls_back_to_the_fixed_one(
    hass: HomeAssistant,
) -> None:
    """A cleared port field falls back to the schema default."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == AIRCO_ID
    assert result["data"][CONF_PORT] == DEFAULT_PORT


@pytest.mark.usefixtures("mock_setup_entry")
async def test_a_retried_submission_keeps_the_identifiers_it_generated(
    hass: HomeAssistant, mock_repository: MagicMock, repository_class: MagicMock
) -> None:
    """A retry reuses the generated ids, as a lost answer still took a slot."""
    mock_repository.async_register.side_effect = [WfRacConnectionError("lost"), None]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    attempts = repository_class.call_args_list
    assert len(attempts) == 2
    assert attempts[0].args[3:5] == attempts[1].args[3:5]
    assert len(attempts[0].args[3]) == 36


@pytest.mark.usefixtures("mock_setup_entry")
async def test_a_second_airco_registers_under_the_same_identifiers(
    hass: HomeAssistant,
    mock_repository: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """One operator id and device id serve every airco of an installation."""
    mock_config_entry.add_to_hass(hass)
    mock_repository.get_airco_id.return_value = "bbccddee1122"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_HOST: "192.168.1.9"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "bbccddee1122"
    assert result["data"][CONF_OPERATOR_ID] == ENTRY_DATA[CONF_OPERATOR_ID]
    assert result["data"][CONF_DEVICE_ID] == ENTRY_DATA[CONF_DEVICE_ID]
