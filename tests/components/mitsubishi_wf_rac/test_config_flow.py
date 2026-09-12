"""Test the Mitsubishi WF-RAC config flow."""

from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

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

USER_INPUT = {CONF_HOST: HOST, CONF_PORT: PORT}


def _discovery_info(
    port: int = PORT, host: str = HOST, airco_id: str = AIRCO_ID
) -> ZeroconfServiceInfo:
    return ZeroconfServiceInfo(
        ip_address=host,
        ip_addresses=[host],
        hostname=f"{airco_id}.local.",
        name=f"{airco_id}._beaver._tcp.local.",
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
    # Named after the unit, not by the user: the flow does not ask for a name,
    # and nothing it stores carries one. Four characters of the airco id are
    # enough to tell two units apart without putting the whole one in the
    # device name and every entity id built from it.
    assert result["title"] == f"WF-RAC {AIRCO_ID[-4:]}"
    assert AIRCO_ID not in result["title"]
    assert CONF_NAME not in result["data"]
    assert result["data"][CONF_AIRCO_ID] == AIRCO_ID
    assert result["data"][CONF_HOST] == HOST
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


async def test_user_flow_registration_answer_without_a_result_code(
    hass: HomeAssistant, mock_repository: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """A module that answers registration without a result code is unreachable.

    Reading the code straight out of the answer would end the flow as an
    unexpected error instead of one the form can explain.
    """
    mock_repository.update_account_info.return_value = {"unexpected": "shape"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


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


async def test_user_flow_input_validation(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """The host is checked before the airco is contacted.

    The error lands on its own field rather than on the form as a whole.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_HOST: "ab"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"][CONF_HOST] == "invalid_host"


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
        result["flow_id"], {CONF_PORT: PORT}
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
        result["flow_id"], {CONF_PORT: 5353}
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
    """A rediscovered airco aborts and refreshes the stored address.

    The address only: an announcement carrying 5353 - the mDNS port itself,
    in the SRV record where the API port belongs - would otherwise be
    written into a working entry and take it offline. The port a configured
    entry has is the one setup established.
    """
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_discovery_info(port=5353, host="192.168.1.9"),
    )

    assert result["type"] is FlowResultType.ABORT
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.9"
    assert mock_config_entry.data[CONF_PORT] == PORT


async def test_a_shouted_hostname_still_matches_the_entry(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The unique id is one case, whoever supplied it.

    Discovery takes it from the announced hostname and every other path from
    the airconId the unit reports. Compared as they arrive, a difference in
    case would offer a configured unit as a new discovery and never refresh
    its address.
    """
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_discovery_info(host="192.168.1.9", airco_id=AIRCO_ID.upper()),
    )

    assert result["type"] is FlowResultType.ABORT
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.9"


async def test_zeroconf_flow_port_fallback_also_fails(
    hass: HomeAssistant, mock_repository: AsyncMock, mock_setup_entry: AsyncMock
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
async def test_unexpected_error_is_shown_not_raised(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    mock_setup_entry: AsyncMock,
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
    assert result["errors"]["base"] == "unexpected_error"


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


async def test_user_flow_refuses_a_unit_that_is_already_configured(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """One unit reached at a second address is not a second airco.

    The manual step has no unique id to abort on, so the identity it matches
    on is the airco id the module reports - the duplicate-host check the user
    can override does not see this case at all.
    """
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_HOST: "192.168.1.9"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_the_port_can_be_cleared_and_falls_back_to_the_fixed_one(
    hass: HomeAssistant, mock_repository: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """A pre-filled value is a suggestion, and a form field can be emptied.

    The port is read with [] during registration, so without a schema default
    an empty field ended the flow in "unexpected_error" rather than using the
    port every firmware branch serves.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PORT] == DEFAULT_PORT


async def test_a_retried_submission_keeps_the_identifiers_it_generated(
    hass: HomeAssistant, mock_repository: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """The module has four account slots and never frees one by itself.

    A registration whose answer was lost has still taken one. Generating a
    fresh operator id per submission would take another on every retry, and
    enough retries would leave no slot to set up with.
    """
    mock_repository.get_airco_id.side_effect = [WfRacConnectionError("lost"), AIRCO_ID]

    with patch(
        "homeassistant.components.mitsubishi_wf_rac.config_flow.uuid4", wraps=uuid4
    ) as generate:
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
    # One operator id and one device id for the whole flow, not a fresh pair
    # for every submission.
    assert generate.call_count == 2


async def test_a_registration_that_cannot_be_reached_says_so(
    hass: HomeAssistant, mock_repository: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Registration is a second request, and the unit can go away between them.

    That is the same connection problem as the query before it, and has to
    read as one instead of as a bug in the flow.
    """
    mock_repository.update_account_info.side_effect = WfRacConnectionError("gone")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"
