"""Tests for the BroadLink Magic config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from broadlink_async.magic import DiscoveredRMMax, Family
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.broadlink.const import (
    CONF_ENTRY_KIND,
    DOMAIN,
    ENTRY_KIND_MAGIC_FAMILY,
)
from homeassistant.components.broadlink.magic_gateway_listener import (
    DATA_GATEWAY_LISTENER,
)
from homeassistant.components.broadlink.magic_helpers import family_to_entry_data
from homeassistant.components.broadlink.magic_import_session import (
    DATA_IMPORT_SESSIONS,
    ImportSession,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType
from homeassistant.helpers.network import NoURLAvailableError

pytestmark = pytest.mark.usefixtures("socket_enabled")


@pytest.fixture(autouse=True)
def mock_setup_entry() -> AsyncMock:
    """Avoid setting up the created entry."""
    with patch(
        "homeassistant.components.broadlink.async_setup_entry",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock:
        yield mock


async def _start_import(
    hass: HomeAssistant,
) -> tuple[FlowResult, ImportSession]:
    with patch(
        "homeassistant.components.broadlink.config_flow.get_url",
        return_value="http://192.0.2.2:8123",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.MENU
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "magic_family"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "magic_family"
    manager = hass.data[DATA_IMPORT_SESSIONS]
    session = manager.active_sessions[0]
    return result, session


async def test_full_import_flow(
    hass: HomeAssistant,
    family: Family,
    gateways: list[DiscoveredRMMax],
) -> None:
    """Test QR import, gateway registration, confirmation, and entry creation."""
    result, session = await _start_import(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.SHOW_PROGRESS

    assert session.complete([family])
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    if result["type"] is FlowResultType.SHOW_PROGRESS_DONE:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "magic_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test home"
    assert result["result"].unique_id == "magic:family-1"
    assert result["data"][CONF_ENTRY_KIND] == ENTRY_KIND_MAGIC_FAMILY
    assert len(result["data"]["gateways"]) == 2


async def test_latest_import_wins_over_unfinished_flow(
    hass: HomeAssistant,
    family: Family,
) -> None:
    """Test a new scan for a family left at confirmation is not aborted."""

    async def import_to_confirm() -> FlowResult:
        result, _ = await _start_import(hass)
        session = next(
            session
            for session in hass.data[DATA_IMPORT_SESSIONS].active_sessions
            if session.flow_id == result["flow_id"]
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert session.complete([family])
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
        if result["type"] is FlowResultType.SHOW_PROGRESS_DONE:
            result = await hass.config_entries.flow.async_configure(result["flow_id"])
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "magic_confirm"
        return result

    stale = await import_to_confirm()
    latest = await import_to_confirm()

    result = await hass.config_entries.flow.async_configure(latest["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert all(
        flow["flow_id"] != stale["flow_id"]
        for flow in hass.config_entries.flow.async_progress()
    )

    stale = await import_to_confirm()
    latest = await import_to_confirm()

    result = await hass.config_entries.flow.async_configure(latest["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert all(
        flow["flow_id"] != stale["flow_id"]
        for flow in hass.config_entries.flow.async_progress()
    )


async def test_duplicate_family(
    hass: HomeAssistant,
    family: Family,
    gateways: list[DiscoveredRMMax],
) -> None:
    """Test reimport updates the existing family entry."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"magic:{family.family_id}",
        data={CONF_ENTRY_KIND: ENTRY_KIND_MAGIC_FAMILY},
    )
    existing.add_to_hass(hass)
    result, session = await _start_import(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert session.complete([family])
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    if result["type"] is FlowResultType.SHOW_PROGRESS_DONE:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "magic_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert existing.data["family_name"] == "Test home"
    assert existing.data["rooms"][1]["name"] == "Living room"
    assert existing.data["groups"][0]["name"] == "Living room lights"
    assert existing.data["scenes"][0]["name"] == "Movie"


async def test_reimport_replaces_saved_gateway_addresses(
    hass: HomeAssistant,
    family: Family,
    gateways: list[DiscoveredRMMax],
) -> None:
    """Test reimport no longer depends on saved runtime gateway addresses."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"magic:{family.family_id}",
        data={
            **family_to_entry_data(family, gateways),
            CONF_ENTRY_KIND: ENTRY_KIND_MAGIC_FAMILY,
        },
    )
    existing.add_to_hass(hass)
    result, session = await _start_import(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert session.complete([family])
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    if result["type"] is FlowResultType.SHOW_PROGRESS_DONE:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "magic_confirm"


async def test_gateway_in_other_family(
    hass: HomeAssistant,
    family: Family,
    gateways: list[DiscoveredRMMax],
) -> None:
    """Test a gateway already used by another family aborts the import."""
    other = Family(
        "family-2", "Other home", "", devices=[family.devices[0]], rooms=family.rooms
    )
    MockConfigEntry(
        domain=DOMAIN,
        title="Other home",
        unique_id="magic:family-2",
        data={
            **family_to_entry_data(other, gateways[:1]),
            CONF_ENTRY_KIND: ENTRY_KIND_MAGIC_FAMILY,
        },
    ).add_to_hass(hass)
    MockConfigEntry(domain=DOMAIN, unique_id="aabbccddeeff", data={}).add_to_hass(hass)
    result, session = await _start_import(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert session.complete([family])
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    if result["type"] is FlowResultType.SHOW_PROGRESS_DONE:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "gateway_in_other_family"
    assert result["description_placeholders"] == {"family": "Other home"}


async def test_gateway_claimed_by_other_family_before_confirm(
    hass: HomeAssistant,
    family: Family,
    gateways: list[DiscoveredRMMax],
) -> None:
    """Test gateway ownership is checked again when the import is confirmed."""
    result, session = await _start_import(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert session.complete([family])
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    if result["type"] is FlowResultType.SHOW_PROGRESS_DONE:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["step_id"] == "magic_confirm"

    other = Family(
        "family-2", "Other home", "", devices=[family.devices[0]], rooms=family.rooms
    )
    MockConfigEntry(
        domain=DOMAIN,
        title="Other home",
        unique_id="magic:family-2",
        data={
            **family_to_entry_data(other, gateways[:1]),
            CONF_ENTRY_KIND: ENTRY_KIND_MAGIC_FAMILY,
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "gateway_in_other_family"
    assert result["description_placeholders"] == {"family": "Other home"}


@pytest.mark.parametrize(
    ("families", "reason"),
    [
        ([], "invalid_import"),
        ([Family("one", "One", ""), Family("two", "Two", "")], "multiple_families"),
        ([Family("one", "One", "")], "no_gateway"),
    ],
)
async def test_invalid_import_results(
    hass: HomeAssistant,
    families: list[Family],
    reason: str,
) -> None:
    """Test invalid imports abort cleanly."""
    result, session = await _start_import(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert session.complete(families)
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    if result["type"] is FlowResultType.SHOW_PROGRESS_DONE:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_no_home_assistant_url(hass: HomeAssistant) -> None:
    """Test setup aborts when no App-reachable URL exists."""
    with patch(
        "homeassistant.components.broadlink.config_flow.get_url",
        side_effect=NoURLAvailableError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "magic_family"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_url"


async def test_import_timeout_and_retry(hass: HomeAssistant) -> None:
    """Test timeout handling creates a fresh QR session."""
    result, first_session = await _start_import(hass)
    with patch(
        "homeassistant.components.broadlink.config_flow.BroadlinkFlowHandler._async_wait_for_magic_import",
        side_effect=TimeoutError,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    if result["type"] is FlowResultType.SHOW_PROGRESS_DONE:
        result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "magic_import_timeout"

    with patch(
        "homeassistant.components.broadlink.config_flow.get_url",
        return_value="http://192.0.2.2:8123",
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "magic_family"
    manager = hass.data[DATA_IMPORT_SESSIONS]
    assert manager.active_sessions[0] is not first_session


async def test_listener_released_when_flow_ends(
    hass: HomeAssistant,
    mock_gateway_listener: MagicMock,
) -> None:
    """Test an abandoned import releases the shared gateway listener."""
    hass.data[DATA_GATEWAY_LISTENER] = mock_gateway_listener
    result, _ = await _start_import(hass)
    hass.config_entries.flow.async_abort(result["flow_id"])
    await hass.async_block_till_done()
    mock_gateway_listener.async_release_flow.assert_awaited_once_with(result["flow_id"])
    assert not hass.data[DATA_IMPORT_SESSIONS].active_sessions


async def test_gateway_port_unavailable(hass: HomeAssistant) -> None:
    """Test the import aborts when the gateway UDP port cannot be bound."""
    with (
        patch(
            "homeassistant.components.broadlink.config_flow.get_url",
            return_value="http://192.0.2.2:8123",
        ),
        patch(
            "homeassistant.components.broadlink.config_flow.async_get_gateway_listener",
            side_effect=OSError,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "magic_family"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_listen"
