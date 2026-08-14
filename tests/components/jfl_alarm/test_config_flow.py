"""The configuration flows: hub, options, and the panel subentry.

Author: Jonis Maurin Ceará <jmceara AT gmail.com>
Based on the code developed by Carlos Jose Fernandes,
available at https://github.com/fernac03/JFL_ACTIVE

The sprint asks for 100% coverage of `config_flow.py`, and for a good reason: a flow is the one
part of an integration the user always meets and the one part no runtime test exercises. A branch
that is never taken here is a dialog that has never been opened.
"""

from __future__ import annotations

import socket

from homeassistant import config_entries
from homeassistant.components.jfl_alarm.const import (
    CONF_KEEPALIVE_MINUTES,
    CONF_LOG_RAW_FRAMES,
    CONF_READ_ONLY,
    CONF_SERIAL,
    CONF_UNKNOWN_PANELS,
    DEFAULT_HOST,
    DOMAIN,
    SUBENTRY_TYPE_PANEL,
    UNKNOWN_HOLD,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import LOOPBACK, free_port, make_entry
from .panel_sim import FakePanel


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


async def test_reconfigure_moves_the_listener(hass: HomeAssistant, setup_entry) -> None:
    """Changing the port rebinds; the entry keeps its identity as the new port."""
    new_port = free_port()
    result = await setup_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: new_port, CONF_HOST: LOOPBACK}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert setup_entry.data[CONF_PORT] == new_port


async def test_reconfigure_to_the_same_port_does_not_probe_its_own_listener(
    hass: HomeAssistant, setup_entry, port: int
) -> None:
    """Re-saving without changing anything must not fail against the listener we are running.

    Without the "did it actually change?" check this is a guaranteed `port_in_use`, and the user
    can never save the form.
    """
    result = await setup_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: port, CONF_HOST: LOOPBACK}
    )
    await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_onto_another_entrys_port_is_refused(
    hass: HomeAssistant, setup_entry
) -> None:
    """Moving one listener onto another's port would give two entries the same identity."""
    other_port = free_port()
    make_entry(other_port).add_to_hass(hass)

    result = await setup_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PORT: other_port, CONF_HOST: LOOPBACK}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_listener"


async def test_reconfigure_reports_a_busy_port(
    hass: HomeAssistant, setup_entry
) -> None:
    """A port someone else holds is a form error on the reconfigure step too."""
    busy = free_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as holder:
        holder.bind((LOOPBACK, busy))
        holder.listen(1)

        result = await setup_entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PORT: busy, CONF_HOST: LOOPBACK}
        )
    assert result["errors"] == {"base": "port_in_use"}


async def test_the_options_flow_saves_every_hub_option(
    hass: HomeAssistant, setup_entry
) -> None:
    """All four options are hub-wide, and changing any of them reloads the entry."""
    result = await hass.config_entries.options.async_init(setup_entry.entry_id)
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_KEEPALIVE_MINUTES: 7,
            CONF_UNKNOWN_PANELS: UNKNOWN_HOLD,
            CONF_LOG_RAW_FRAMES: True,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert setup_entry.options[CONF_KEEPALIVE_MINUTES] == 7
    assert setup_entry.options[CONF_UNKNOWN_PANELS] == UNKNOWN_HOLD
    assert setup_entry.options[CONF_LOG_RAW_FRAMES] is True

    # And they reached the running listener, not just the stored options.
    server = setup_entry.runtime_data.server
    assert server.keepalive_minutes == 7
    assert server.log_raw_frames is True
    assert server.unknown_panels == UNKNOWN_HOLD


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


async def test_a_pending_panel_is_offered_and_names_itself(
    hass: HomeAssistant, port: int, connect_panel
) -> None:
    """A panel held for approval is picked from a list, model name and all."""
    entry = make_entry(port, serials=[], options={CONF_UNKNOWN_PANELS: UNKNOWN_HOLD})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    try:
        panel = FakePanel(serial="PENDING001", model_byte=0xA0)
        connection = await connect_panel(panel)
        await connection.introduce(hass)

        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_TYPE_PANEL),
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                CONF_SERIAL: panel.serial,
                CONF_READ_ONLY: True,
            },
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        # The title comes from the panel's own model byte, not from anything the user typed.
        assert result["title"] == "Active 32 Duo PENDING001"
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


async def test_the_panel_list_is_empty_when_the_entry_is_not_loaded(
    hass: HomeAssistant, entry
) -> None:
    """The list of panels that dialled in is a convenience, never a prerequisite."""
    entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_PANEL),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
