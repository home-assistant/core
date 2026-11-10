"""Test the AlarmDecoder config flow."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from alarmdecoder.util import NoDeviceError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.alarmdecoder import config_flow
from homeassistant.components.alarmdecoder.const import (
    CONF_ALT_NIGHT_MODE,
    CONF_AUTO_BYPASS,
    CONF_CODE_ARM_REQUIRED,
    CONF_DEVICE_BAUD,
    CONF_DEVICE_PATH,
    CONF_RELAY_ADDR,
    CONF_RELAY_CHAN,
    CONF_ZONE_LOOP,
    CONF_ZONE_NAME,
    CONF_ZONE_NUMBER,
    CONF_ZONE_RFID,
    CONF_ZONE_TYPE,
    DEFAULT_ARM_OPTIONS,
    DEFAULT_ZONE_OPTIONS,
    DOMAIN,
    OPTIONS_ARM,
    OPTIONS_ZONES,
    PROTOCOL_SERIAL,
    PROTOCOL_SOCKET,
)
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_PROTOCOL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.parametrize(
    ("protocol", "connection", "title"),
    [
        (
            PROTOCOL_SOCKET,
            {
                CONF_HOST: "alarmdecoder123",
                CONF_PORT: 10001,
            },
            "alarmdecoder123:10001",
        ),
        (
            PROTOCOL_SERIAL,
            {
                CONF_DEVICE_PATH: "/dev/ttyUSB123",
                CONF_DEVICE_BAUD: 115000,
            },
            "/dev/ttyUSB123",
        ),
    ],
)
async def test_setups(hass: HomeAssistant, protocol, connection, title) -> None:
    """Test flow for setting up the available AlarmDecoder protocols."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PROTOCOL: protocol},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "protocol"

    with (
        patch("homeassistant.components.alarmdecoder.config_flow.AdExt.open"),
        patch("homeassistant.components.alarmdecoder.config_flow.AdExt.close"),
        patch(
            "homeassistant.components.alarmdecoder.async_setup_entry",
            return_value=None,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], connection
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == title
        assert result["data"] == {
            **connection,
            CONF_PROTOCOL: protocol,
        }
        await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 1


async def test_setup_connection_error(hass: HomeAssistant) -> None:
    """Test flow for setup with a connection error."""

    port = 1001
    host = "alarmdecoder"
    protocol = PROTOCOL_SOCKET
    connection_settings = {CONF_HOST: host, CONF_PORT: port}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PROTOCOL: protocol},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "protocol"

    with (
        patch(
            "homeassistant.components.alarmdecoder.config_flow.AdExt.open",
            side_effect=NoDeviceError,
        ),
        patch("homeassistant.components.alarmdecoder.config_flow.AdExt.close"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], connection_settings
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

    with (
        patch(
            "homeassistant.components.alarmdecoder.config_flow.AdExt.open",
            side_effect=Exception,
        ),
        patch("homeassistant.components.alarmdecoder.config_flow.AdExt.close"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], connection_settings
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}

    with (
        patch("homeassistant.components.alarmdecoder.config_flow.AdExt.open"),
        patch("homeassistant.components.alarmdecoder.config_flow.AdExt.close"),
        patch(
            "homeassistant.components.alarmdecoder.async_setup_entry",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], connection_settings
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_arm_flow(hass: HomeAssistant) -> None:
    """Test arm options flow."""
    user_input = {
        CONF_ALT_NIGHT_MODE: True,
        CONF_AUTO_BYPASS: True,
        CONF_CODE_ARM_REQUIRED: True,
    }
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"edit_selection": "Arming Settings"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "arm_settings"

    with patch(
        "homeassistant.components.alarmdecoder.async_setup_entry", return_value=None
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        OPTIONS_ARM: user_input,
        OPTIONS_ZONES: DEFAULT_ZONE_OPTIONS,
    }


async def test_options_zone_flow(hass: HomeAssistant) -> None:
    """Test options flow for adding/deleting zones."""
    zone_number = "2"
    zone_settings = {
        CONF_ZONE_NAME: "Front Entry",
        CONF_ZONE_TYPE: BinarySensorDeviceClass.WINDOW,
    }
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"edit_selection": "Zones"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zone_select"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ZONE_NUMBER: zone_number},
    )

    with patch(
        "homeassistant.components.alarmdecoder.async_setup_entry", return_value=None
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=zone_settings,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        OPTIONS_ARM: DEFAULT_ARM_OPTIONS,
        OPTIONS_ZONES: {zone_number: zone_settings},
    }

    # Make sure zone can be removed...
    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"edit_selection": "Zones"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zone_select"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ZONE_NUMBER: zone_number},
    )

    with patch(
        "homeassistant.components.alarmdecoder.async_setup_entry", return_value=None
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        OPTIONS_ARM: DEFAULT_ARM_OPTIONS,
        OPTIONS_ZONES: {},
    }


async def test_options_zone_flow_validation(hass: HomeAssistant) -> None:
    """Test input validation for zone options flow."""
    zone_number = "2"
    zone_settings = {
        CONF_ZONE_NAME: "Front Entry",
        CONF_ZONE_TYPE: BinarySensorDeviceClass.WINDOW,
    }
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"edit_selection": "Zones"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zone_select"

    # Zone Number must be int
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ZONE_NUMBER: "asd"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zone_select"
    assert result["errors"] == {CONF_ZONE_NUMBER: "int"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_ZONE_NUMBER: zone_number},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zone_details"

    # CONF_RELAY_ADDR & CONF_RELAY_CHAN are inclusive
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={**zone_settings, CONF_RELAY_ADDR: "1"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zone_details"
    assert result["errors"] == {"base": "relay_inclusive"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={**zone_settings, CONF_RELAY_CHAN: "1"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zone_details"
    assert result["errors"] == {"base": "relay_inclusive"}

    # CONF_RELAY_ADDR, CONF_RELAY_CHAN must be int
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={**zone_settings, CONF_RELAY_ADDR: "abc", CONF_RELAY_CHAN: "abc"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zone_details"
    assert result["errors"] == {
        CONF_RELAY_ADDR: "int",
        CONF_RELAY_CHAN: "int",
    }

    # CONF_ZONE_LOOP depends on CONF_ZONE_RFID
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={**zone_settings, CONF_ZONE_LOOP: "1"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zone_details"
    assert result["errors"] == {CONF_ZONE_LOOP: "loop_rfid"}

    # CONF_ZONE_LOOP must be int
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={**zone_settings, CONF_ZONE_RFID: "rfid123", CONF_ZONE_LOOP: "ab"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zone_details"
    assert result["errors"] == {CONF_ZONE_LOOP: "int"}

    # CONF_ZONE_LOOP must be between [1,4]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={**zone_settings, CONF_ZONE_RFID: "rfid123", CONF_ZONE_LOOP: "5"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zone_details"
    assert result["errors"] == {CONF_ZONE_LOOP: "loop_range"}

    # All valid settings
    with patch(
        "homeassistant.components.alarmdecoder.async_setup_entry", return_value=None
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                **zone_settings,
                CONF_ZONE_RFID: "rfid123",
                CONF_ZONE_LOOP: "2",
                CONF_RELAY_ADDR: "12",
                CONF_RELAY_CHAN: "1",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        OPTIONS_ARM: DEFAULT_ARM_OPTIONS,
        OPTIONS_ZONES: {
            zone_number: {
                **zone_settings,
                CONF_ZONE_RFID: "rfid123",
                CONF_ZONE_LOOP: 2,
                CONF_RELAY_ADDR: 12,
                CONF_RELAY_CHAN: 1,
            }
        },
    }


@pytest.mark.parametrize(
    ("protocol", "connection"),
    [
        (
            PROTOCOL_SOCKET,
            {
                CONF_HOST: "alarmdecoder123",
                CONF_PORT: 10001,
            },
        ),
        (
            PROTOCOL_SERIAL,
            {
                CONF_DEVICE_PATH: "/dev/ttyUSB123",
                CONF_DEVICE_BAUD: 115000,
            },
        ),
    ],
)
async def test_one_device_allowed(hass: HomeAssistant, protocol, connection) -> None:
    """Test that only one AlarmDecoder device is allowed."""
    flow = config_flow.AlarmDecoderFlowHandler()
    flow.hass = hass

    MockConfigEntry(
        domain=DOMAIN,
        data=connection,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PROTOCOL: protocol},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "protocol"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], connection
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.fixture
def mock_controller() -> Generator[MagicMock]:
    """Patch the controller the integration sets up with after a reload."""
    with (
        patch("homeassistant.components.alarmdecoder.AdExt") as mock_adext,
        patch("homeassistant.components.alarmdecoder.PLATFORMS", []),
    ):
        mock_adext.return_value.is_init = AsyncMock(return_value=True)
        yield mock_adext.return_value


@pytest.mark.parametrize(
    ("protocol", "old_title", "old", "new", "title"),
    [
        pytest.param(
            PROTOCOL_SOCKET,
            "alarmdecoder.local:10000",
            {CONF_HOST: "alarmdecoder.local", CONF_PORT: 10000},
            {CONF_HOST: "alarmdecoder.example.com", CONF_PORT: 10001},
            "alarmdecoder.example.com:10001",
            id="socket",
        ),
        pytest.param(
            PROTOCOL_SERIAL,
            "/dev/ttyUSB0",
            {CONF_DEVICE_PATH: "/dev/ttyUSB0", CONF_DEVICE_BAUD: 115200},
            {CONF_DEVICE_PATH: "/dev/ttyUSB1", CONF_DEVICE_BAUD: 115200},
            "/dev/ttyUSB1",
            id="serial",
        ),
    ],
)
async def test_reconfigure(
    hass: HomeAssistant,
    mock_controller: MagicMock,
    protocol: str,
    old_title: str,
    old: dict[str, Any],
    new: dict[str, Any],
    title: str,
) -> None:
    """Test changing the connection settings keeps the entry and its options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=old_title,
        data={CONF_PROTOCOL: protocol, **old},
        options={OPTIONS_ZONES: {"1": {CONF_ZONE_NAME: "Front Door"}}},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with (
        patch("homeassistant.components.alarmdecoder.config_flow.AdExt.open"),
        patch("homeassistant.components.alarmdecoder.config_flow.AdExt.close"),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], new)
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_PROTOCOL: protocol, **new}
    assert entry.title == title
    assert entry.options == {OPTIONS_ZONES: {"1": {CONF_ZONE_NAME: "Front Door"}}}
    assert entry.state is ConfigEntryState.LOADED
    # Set up once, then reloaded exactly once.
    assert mock_controller.open.call_count == 2


async def test_reconfigure_keeps_custom_title(
    hass: HomeAssistant, mock_controller: MagicMock
) -> None:
    """Test a title the user chose survives a reconfigure."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Alarm panel",
        data={CONF_PROTOCOL: PROTOCOL_SOCKET, CONF_HOST: "old", CONF_PORT: 10000},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    with (
        patch("homeassistant.components.alarmdecoder.config_flow.AdExt.open"),
        patch("homeassistant.components.alarmdecoder.config_flow.AdExt.close"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "new", CONF_PORT: 10000}
        )
        await hass.async_block_till_done()

    assert result["reason"] == "reconfigure_successful"
    assert entry.title == "Alarm panel"
    assert entry.data[CONF_HOST] == "new"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [(NoDeviceError, "cannot_connect"), (Exception, "unknown")],
)
async def test_reconfigure_errors(
    hass: HomeAssistant,
    mock_controller: MagicMock,
    side_effect: type[Exception],
    error: str,
) -> None:
    """Test a failed connection test leaves the entry alone and can be retried."""
    old = {CONF_PROTOCOL: PROTOCOL_SOCKET, CONF_HOST: "old", CONF_PORT: 10000}
    entry = MockConfigEntry(domain=DOMAIN, title="old:10000", data=old)
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    with (
        patch(
            "homeassistant.components.alarmdecoder.config_flow.AdExt.open",
            side_effect=side_effect,
        ),
        patch("homeassistant.components.alarmdecoder.config_flow.AdExt.close"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "new", CONF_PORT: 10000}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert entry.data == old

    with (
        patch("homeassistant.components.alarmdecoder.config_flow.AdExt.open"),
        patch("homeassistant.components.alarmdecoder.config_flow.AdExt.close"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "new", CONF_PORT: 10000}
        )
        await hass.async_block_till_done()

    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "new"


async def test_reconfigure_to_other_entrys_device(hass: HomeAssistant) -> None:
    """Test reconfiguring onto a device another entry already uses aborts."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PROTOCOL: PROTOCOL_SOCKET, CONF_HOST: "taken", CONF_PORT: 10000},
    ).add_to_hass(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_PROTOCOL: PROTOCOL_SOCKET, CONF_HOST: "mine", CONF_PORT: 10000},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "taken", CONF_PORT: 10000}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "mine"
