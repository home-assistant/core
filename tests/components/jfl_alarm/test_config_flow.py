"""The configuration flows: hub, options, and the panel subentry.

The sprint asks for 100% coverage of `config_flow.py`, and for a good reason: a flow is the one
part of an integration the user always meets and the one part no runtime test exercises. A branch
that is never taken here is a dialog that has never been opened.
"""

from __future__ import annotations

import socket

from homeassistant import config_entries
from homeassistant.components.jfl_alarm.const import (
    CONF_READ_ONLY,
    CONF_SERIAL,
    DEFAULT_HOST,
    DOMAIN,
    SUBENTRY_TYPE_PANEL,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import LOOPBACK, make_entry


async def test_the_user_step_only_asks_for_a_port(
    hass: HomeAssistant, port: int
) -> None:
    """One question, because everything else comes from the panel."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert set(result["data_schema"].schema) == {CONF_PORT, CONF_HOST}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: port, CONF_HOST: LOOPBACK}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: LOOPBACK, CONF_PORT: port}
    assert result["result"].unique_id == str(port)

    await hass.config_entries.async_unload(result["result"].entry_id)
    await hass.async_block_till_done()


async def test_an_empty_host_falls_back_to_every_interface(
    hass: HomeAssistant, port: int
) -> None:
    """Blanking the address must mean "everywhere", never "loopback only"."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: port, CONF_HOST: "   "}
    )
    await hass.async_block_till_done()

    assert result["data"][CONF_HOST] == DEFAULT_HOST
    await hass.config_entries.async_unload(result["result"].entry_id)
    await hass.async_block_till_done()


async def test_a_busy_port_is_reported_as_a_form_error(
    hass: HomeAssistant, port: int
) -> None:
    """The bind is tested before the entry is created, so the user finds out immediately."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as holder:
        holder.bind((LOOPBACK, port))
        holder.listen(1)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PORT: port, CONF_HOST: LOOPBACK}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "port_in_use"}

    # And the same flow succeeds once the port is free, rather than being stuck.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: port, CONF_HOST: LOOPBACK}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.config_entries.async_unload(result["result"].entry_id)
    await hass.async_block_till_done()


async def test_a_second_listener_on_the_same_port_is_refused(
    hass: HomeAssistant, port: int
) -> None:
    """The port is the entry's identity: two listeners on one port cannot both work."""
    make_entry(port).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: port, CONF_HOST: LOOPBACK}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_a_panel_can_be_added_by_hand(hass: HomeAssistant, port: int) -> None:
    """For the installation where the panel is not powered up yet."""
    entry = make_entry(port, serials=[])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    try:
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_TYPE_PANEL),
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_SERIAL: "  MANUAL0001  ",
                CONF_READ_ONLY: True,
            },
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "JFL panel MANUAL0001"
        [subentry] = list(entry.subentries.values())
        assert subentry.data[CONF_SERIAL] == "MANUAL0001"
    finally:
        if entry.state.recoverable:
            await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()


async def test_an_empty_serial_is_rejected(hass: HomeAssistant, setup_entry) -> None:
    """The serial is the panel's identity, so it cannot be blank."""
    result = await hass.config_entries.subentries.async_init(
        (setup_entry.entry_id, SUBENTRY_TYPE_PANEL),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_SERIAL: "   ", CONF_READ_ONLY: True},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_SERIAL: "invalid_serial"}


async def test_adding_the_same_panel_twice_aborts(
    hass: HomeAssistant, setup_entry
) -> None:
    """The subentry for a panel already configured must not be created a second time."""
    result = await hass.config_entries.subentries.async_init(
        (setup_entry.entry_id, SUBENTRY_TYPE_PANEL),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            CONF_SERIAL: "0000000001",
            CONF_READ_ONLY: True,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_a_panel_subentry_can_be_reconfigured(
    hass: HomeAssistant, setup_entry
) -> None:
    """Read-only is per panel, and the serial is not editable."""
    [subentry] = list(setup_entry.subentries.values())
    result = await setup_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    assert result["step_id"] == "reconfigure"
    assert CONF_SERIAL not in result["data_schema"].schema

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_READ_ONLY: False}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    updated = setup_entry.subentries[subentry.subentry_id]
    assert updated.data[CONF_READ_ONLY] is False
    # The serial survived: it is the panel's identity and every unique id derives from it.
    assert updated.data[CONF_SERIAL] == "0000000001"
