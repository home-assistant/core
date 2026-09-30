"""Tests for the Keyboard Remote config flow."""

from collections.abc import Iterator
from contextlib import contextmanager
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.keyboard_remote.config_flow import (
    _get_device_name,
    _resolve_yaml_device,
)
from homeassistant.components.keyboard_remote.const import (
    CONF_DEVICE_DESCRIPTOR,
    CONF_DEVICE_NAME,
    CONF_DEVICE_PATH,
    CONF_EMULATE_KEY_HOLD,
    CONF_EMULATE_KEY_HOLD_DELAY,
    CONF_EMULATE_KEY_HOLD_REPEAT,
    CONF_KEY_TYPES,
    DEFAULT_EMULATE_KEY_HOLD,
    DEFAULT_EMULATE_KEY_HOLD_DELAY,
    DEFAULT_EMULATE_KEY_HOLD_REPEAT,
    DEFAULT_KEY_TYPES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import selector

from .conftest import (
    BUS_BLUETOOTH,
    BUS_HOST,
    EV_KEY,
    FAKE_BY_ID_BASENAME,
    FAKE_DEVICE_NAME,
    FAKE_DEVICE_NAME_2,
    FAKE_DEVICE_PATH,
    FAKE_DEVICE_PATH_2,
    FAKE_DEVICE_REAL_PATH,
)

from tests.common import MockConfigEntry

MOCK_SCAN_RESULT = [
    selector.SelectOptionDict(
        value=FAKE_DEVICE_PATH,
        label=f"{FAKE_DEVICE_NAME} ({FAKE_BY_ID_BASENAME})",
    ),
    selector.SelectOptionDict(
        value=FAKE_DEVICE_PATH_2,
        label=f"{FAKE_DEVICE_NAME_2} (usb-Test_Remote-event-kbd)",
    ),
]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_creates_entry(hass: HomeAssistant) -> None:
    """Test user step shows a form and creates a config entry on valid selection."""
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._scan_input_devices_sync",
        return_value=MOCK_SCAN_RESULT,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.keyboard_remote.config_flow._get_device_name",
        return_value=FAKE_DEVICE_NAME,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE_PATH: FAKE_DEVICE_PATH},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == FAKE_DEVICE_NAME
    assert result["result"].unique_id == FAKE_BY_ID_BASENAME
    assert result["data"] == {
        CONF_DEVICE_PATH: FAKE_DEVICE_PATH,
        CONF_DEVICE_NAME: FAKE_DEVICE_NAME,
    }
    assert result["options"] == {
        CONF_KEY_TYPES: DEFAULT_KEY_TYPES,
        CONF_EMULATE_KEY_HOLD: DEFAULT_EMULATE_KEY_HOLD,
        CONF_EMULATE_KEY_HOLD_DELAY: DEFAULT_EMULATE_KEY_HOLD_DELAY,
        CONF_EMULATE_KEY_HOLD_REPEAT: DEFAULT_EMULATE_KEY_HOLD_REPEAT,
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_cannot_connect(hass: HomeAssistant) -> None:
    """Test user step shows error when device cannot be opened."""
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._scan_input_devices_sync",
        return_value=MOCK_SCAN_RESULT,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    with (
        patch(
            "homeassistant.components.keyboard_remote.config_flow._get_device_name",
            return_value=None,
        ),
        patch(
            "homeassistant.components.keyboard_remote.config_flow._scan_input_devices_sync",
            return_value=MOCK_SCAN_RESULT,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE_PATH: FAKE_DEVICE_PATH},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Retry with a working device — flow should recover
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._get_device_name",
        return_value=FAKE_DEVICE_NAME,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE_PATH: FAKE_DEVICE_PATH},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == FAKE_DEVICE_NAME


async def test_user_step_no_devices(hass: HomeAssistant) -> None:
    """Test user step aborts when no devices found."""
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._scan_input_devices_sync",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_all_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user step aborts when all devices are already configured."""
    # Add an existing entry for the only device in scan results
    single_device = [MOCK_SCAN_RESULT[0]]
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.keyboard_remote.config_flow._scan_input_devices_sync",
        return_value=single_device,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "all_devices_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user step filters out already-configured devices."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.keyboard_remote.config_flow._scan_input_devices_sync",
        return_value=MOCK_SCAN_RESULT,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    # Should show form with only the second device (first is configured)
    assert result["type"] is FlowResultType.FORM

    # The second device can still be configured
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._get_device_name",
        return_value=FAKE_DEVICE_NAME_2,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE_PATH: FAKE_DEVICE_PATH_2},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_PATH] == FAKE_DEVICE_PATH_2


BT_REMOTE_NAME = "BT Remote"


def _input_device(
    name: str, *, sends_keys: bool = True, bustype: int = BUS_BLUETOOTH
) -> MagicMock:
    """Create an evdev device that reports key events or only switch events."""
    dev = MagicMock()
    dev.name = name
    dev.capabilities.return_value = {EV_KEY if sends_keys else 5: [30]}
    dev.info.bustype = bustype
    return dev


@contextmanager
def _input_devices(
    devices: dict[str, MagicMock | None],
    by_id_links: dict[str, str] | None,
) -> Iterator[None]:
    """Mock the event nodes and, unless None, the by-id links pointing at them.

    A device of None cannot be opened.
    """
    entries = []
    for link in by_id_links or {}:
        entry = MagicMock(spec_set=os.DirEntry)
        entry.is_symlink.return_value = True
        entry.path = link
        entries.append(entry)
    not_a_link = MagicMock(spec_set=os.DirEntry)
    not_a_link.is_symlink.return_value = False
    entries.append(not_a_link)
    scandir = MagicMock()
    scandir.return_value.__enter__.return_value = entries

    def _open(path: str) -> MagicMock:
        if (dev := devices[path]) is None:
            raise OSError(13, "Permission denied")
        return dev

    with (
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.path.isdir",
            return_value=by_id_links is not None,
        ),
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.scandir", scandir
        ),
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.path.realpath",
            side_effect=lambda p: (by_id_links or {}).get(p, p),
        ),
        patch("evdev.list_devices", return_value=list(devices)),
        patch("evdev.InputDevice", side_effect=_open),
    ):
        yield


async def test_user_step_lists_devices_without_by_id_link(
    hass: HomeAssistant,
) -> None:
    """Test devices without a by-id link are offered once per name.

    udev creates no by-id link for Bluetooth devices. Nodes that cannot send
    keys, host-bus devices such as the power button, and nodes that cannot be
    opened are not offered.
    """
    devices = {
        FAKE_DEVICE_REAL_PATH: _input_device(FAKE_DEVICE_NAME),
        "/dev/input/event7": _input_device(BT_REMOTE_NAME),
        "/dev/input/event8": _input_device(BT_REMOTE_NAME),
        "/dev/input/event9": _input_device("Headphone Jack", sends_keys=False),
        "/dev/input/event10": None,
        "/dev/input/event11": _input_device("Power Button", bustype=BUS_HOST),
    }
    with _input_devices(devices, {FAKE_DEVICE_PATH: FAKE_DEVICE_REAL_PATH}):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["data_schema"].schema[CONF_DEVICE_PATH].config["options"] == [
        {
            "value": FAKE_DEVICE_PATH,
            "label": f"{FAKE_DEVICE_NAME} ({FAKE_BY_ID_BASENAME})",
        },
        {"value": "/dev/input/event7", "label": f"{BT_REMOTE_NAME} (event7)"},
    ]
    for path in (FAKE_DEVICE_REAL_PATH, "/dev/input/event7", "/dev/input/event8"):
        devices[path].close.assert_called_once()
    devices["/dev/input/event9"].close.assert_called_once()
    devices["/dev/input/event11"].close.assert_called_once()


@pytest.mark.parametrize(
    "by_id_links",
    [pytest.param(None, id="no_by_id_directory"), pytest.param({}, id="no_links")],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_creates_name_matched_entry(
    hass: HomeAssistant,
    by_id_links: dict[str, str] | None,
) -> None:
    """Test a device without a by-id link is configured by its name.

    Its event node can change when it reconnects, so the entry matches by
    name, like a YAML entry configured by name.
    """
    devices = {"/dev/input/event7": _input_device(BT_REMOTE_NAME)}
    with _input_devices(devices, by_id_links):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE_PATH: "/dev/input/event7"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == BT_REMOTE_NAME
    assert result["result"].unique_id == BT_REMOTE_NAME
    assert result["data"] == {CONF_DEVICE_NAME: BT_REMOTE_NAME}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_hides_configured_name_matched_device(
    hass: HomeAssistant,
) -> None:
    """Test a device already configured by name is not offered again."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=BT_REMOTE_NAME,
        data={CONF_DEVICE_NAME: BT_REMOTE_NAME},
    ).add_to_hass(hass)
    devices = {
        FAKE_DEVICE_REAL_PATH: _input_device(FAKE_DEVICE_NAME),
        "/dev/input/event7": _input_device(BT_REMOTE_NAME),
    }
    with _input_devices(devices, {FAKE_DEVICE_PATH: FAKE_DEVICE_REAL_PATH}):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert [
        option["value"]
        for option in result["data_schema"].schema[CONF_DEVICE_PATH].config["options"]
    ] == [FAKE_DEVICE_PATH]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_name_matched_device_configured_meanwhile(
    hass: HomeAssistant,
) -> None:
    """Test submitting a device configured by name in the meantime aborts."""
    devices = {"/dev/input/event7": _input_device(BT_REMOTE_NAME)}
    with _input_devices(devices, {}):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        MockConfigEntry(
            domain=DOMAIN,
            unique_id=BT_REMOTE_NAME,
            data={CONF_DEVICE_NAME: BT_REMOTE_NAME},
        ).add_to_hass(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_DEVICE_PATH: "/dev/input/event7"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_hides_device_configured_by_raw_path(
    hass: HomeAssistant,
) -> None:
    """Test a device imported before its by-id link existed is not offered again.

    That entry is keyed by the raw descriptor, so only the resolved node shows
    that the by-id link now listed points at the same device.
    """
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=FAKE_DEVICE_REAL_PATH,
        data={
            CONF_DEVICE_PATH: FAKE_DEVICE_REAL_PATH,
            CONF_DEVICE_NAME: FAKE_DEVICE_NAME,
            CONF_DEVICE_DESCRIPTOR: FAKE_DEVICE_REAL_PATH,
        },
    ).add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.keyboard_remote.config_flow._scan_input_devices_sync",
            return_value=[MOCK_SCAN_RESULT[0]],
        ),
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.path.realpath",
            side_effect=lambda p: {FAKE_DEVICE_PATH: FAKE_DEVICE_REAL_PATH}.get(p, p),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "all_devices_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_offers_device_on_reused_yaml_descriptor(
    hass: HomeAssistant,
) -> None:
    """Test a device on an eventN named by an old YAML descriptor is offered.

    The imported entry has its own by-id path, and runtime matching ignores the
    descriptor, so the device now on that node is unrelated.
    """
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=FAKE_BY_ID_BASENAME,
        data={
            CONF_DEVICE_PATH: FAKE_DEVICE_PATH,
            CONF_DEVICE_NAME: FAKE_DEVICE_NAME,
            CONF_DEVICE_DESCRIPTOR: FAKE_DEVICE_REAL_PATH,
        },
    ).add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.keyboard_remote.config_flow._scan_input_devices_sync",
            return_value=[MOCK_SCAN_RESULT[1]],
        ),
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.path.realpath",
            side_effect=lambda p: {FAKE_DEVICE_PATH_2: FAKE_DEVICE_REAL_PATH}.get(p, p),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["data_schema"].schema[CONF_DEVICE_PATH].config["options"] == [
        MOCK_SCAN_RESULT[1]
    ]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_with_descriptor_and_by_id(hass: HomeAssistant) -> None:
    """Test YAML import resolves descriptor to by-id path."""
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._resolve_yaml_device",
        return_value=(FAKE_DEVICE_PATH, FAKE_DEVICE_NAME, FAKE_BY_ID_BASENAME),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                "device_descriptor": FAKE_DEVICE_REAL_PATH,
                "type": ["key_up", "key_down"],
                "emulate_key_hold": True,
                "emulate_key_hold_delay": 0.5,
                "emulate_key_hold_repeat": 0.05,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == FAKE_DEVICE_NAME
    assert result["result"].unique_id == FAKE_BY_ID_BASENAME
    assert result["data"][CONF_DEVICE_PATH] == FAKE_DEVICE_PATH
    assert result["data"][CONF_DEVICE_NAME] == FAKE_DEVICE_NAME
    assert result["data"][CONF_DEVICE_DESCRIPTOR] == FAKE_DEVICE_REAL_PATH
    assert result["options"][CONF_KEY_TYPES] == ["key_up", "key_down"]
    assert result["options"][CONF_EMULATE_KEY_HOLD] is True
    assert result["options"][CONF_EMULATE_KEY_HOLD_DELAY] == 0.5
    assert result["options"][CONF_EMULATE_KEY_HOLD_REPEAT] == 0.05


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_with_name(hass: HomeAssistant) -> None:
    """Test YAML import with device_name resolves to by-id."""
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._resolve_yaml_device",
        return_value=(FAKE_DEVICE_PATH, FAKE_DEVICE_NAME, FAKE_BY_ID_BASENAME),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={"device_name": FAKE_DEVICE_NAME},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == FAKE_BY_ID_BASENAME
    assert result["data"][CONF_DEVICE_PATH] == FAKE_DEVICE_PATH
    assert result["data"][CONF_DEVICE_NAME] == FAKE_DEVICE_NAME


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_fallback_no_by_id(hass: HomeAssistant) -> None:
    """Test YAML import falls back to raw path when no by-id link exists."""
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._resolve_yaml_device",
        return_value=(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={"device_descriptor": FAKE_DEVICE_REAL_PATH},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_PATH] == FAKE_DEVICE_REAL_PATH
    assert result["data"][CONF_DEVICE_DESCRIPTOR] == FAKE_DEVICE_REAL_PATH


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_fallback_name_only(hass: HomeAssistant) -> None:
    """Test YAML import with name when no by-id or device found."""
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._resolve_yaml_device",
        return_value=(None, None, None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={"device_name": FAKE_DEVICE_NAME},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == FAKE_DEVICE_NAME
    assert CONF_DEVICE_PATH not in result["data"]
    assert result["data"][CONF_DEVICE_NAME] == FAKE_DEVICE_NAME


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_name_only_discards_transient_path(hass: HomeAssistant) -> None:
    """Test a name-only import stores no path when the device has no by-id link.

    The resolved /dev/input/eventN is whatever the kernel assigned this boot and
    can belong to an unrelated device after the next one, so storing it would
    let it outrank the name the user actually configured.
    """
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._resolve_yaml_device",
        return_value=(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={"device_name": FAKE_DEVICE_NAME},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == FAKE_DEVICE_NAME
    assert CONF_DEVICE_PATH not in result["data"]
    assert result["data"][CONF_DEVICE_NAME] == FAKE_DEVICE_NAME


@pytest.mark.parametrize(
    ("import_data", "legacy_unique_id"),
    [
        pytest.param(
            {"device_descriptor": FAKE_DEVICE_REAL_PATH},
            FAKE_DEVICE_REAL_PATH,
            id="descriptor",
        ),
        pytest.param(
            {"device_name": FAKE_DEVICE_NAME},
            FAKE_DEVICE_NAME,
            id="name",
        ),
    ],
)
async def test_import_adopts_entry_created_before_by_id_existed(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    import_data: dict[str, str],
    legacy_unique_id: str,
) -> None:
    """Test a re-import migrates the earlier entry instead of duplicating it.

    The first import can run before udev has created the by-id symlink, which
    leaves the entry keyed by the raw descriptor or name. Once the symlink
    exists the same YAML resolves to the by-id basename.
    """
    existing = MockConfigEntry(
        domain=DOMAIN,
        unique_id=legacy_unique_id,
        data={CONF_DEVICE_PATH: legacy_unique_id, CONF_DEVICE_NAME: FAKE_DEVICE_NAME},
    )
    existing.add_to_hass(hass)

    with patch(
        "homeassistant.components.keyboard_remote.config_flow._resolve_yaml_device",
        return_value=(FAKE_DEVICE_PATH, FAKE_DEVICE_NAME, FAKE_BY_ID_BASENAME),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=import_data,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert existing.unique_id == FAKE_BY_ID_BASENAME
    assert existing.data[CONF_DEVICE_PATH] == FAKE_DEVICE_PATH
    # Reloaded so the new identity is scanned for, not only matched on events
    await hass.async_block_till_done()
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(
    ("title", "expected_title"),
    [
        pytest.param(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, id="fallback_title"),
        pytest.param("Living room remote", "Living room remote", id="user_title"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_adoption_refreshes_fallback_name(
    hass: HomeAssistant,
    title: str,
    expected_title: str,
) -> None:
    """Test adoption replaces the raw path stored as name when the device was absent.

    A title the user has changed since is kept.
    """
    existing = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FAKE_DEVICE_REAL_PATH,
        title=title,
        data={
            CONF_DEVICE_PATH: FAKE_DEVICE_REAL_PATH,
            CONF_DEVICE_NAME: FAKE_DEVICE_REAL_PATH,
            CONF_DEVICE_DESCRIPTOR: FAKE_DEVICE_REAL_PATH,
        },
    )
    existing.add_to_hass(hass)

    with patch(
        "homeassistant.components.keyboard_remote.config_flow._resolve_yaml_device",
        return_value=(FAKE_DEVICE_PATH, FAKE_DEVICE_NAME, FAKE_BY_ID_BASENAME),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={"device_descriptor": FAKE_DEVICE_REAL_PATH},
        )

    assert result["type"] is FlowResultType.ABORT
    assert existing.data[CONF_DEVICE_NAME] == FAKE_DEVICE_NAME
    assert existing.title == expected_title


@pytest.mark.parametrize(
    ("import_data", "legacy_unique_id"),
    [
        pytest.param(
            {"device_descriptor": FAKE_DEVICE_REAL_PATH},
            FAKE_DEVICE_REAL_PATH,
            id="descriptor",
        ),
        pytest.param(
            {"device_name": FAKE_DEVICE_NAME},
            FAKE_DEVICE_NAME,
            id="name",
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_does_not_adopt_onto_a_taken_unique_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    import_data: dict[str, str],
    legacy_unique_id: str,
) -> None:
    """Test the legacy entry is left alone when the by-id ID is already in use.

    The user added the device through the UI before the YAML was re-imported,
    so adopting would give both entries the same unique ID.
    """
    mock_config_entry.add_to_hass(hass)
    legacy = MockConfigEntry(
        domain=DOMAIN,
        unique_id=legacy_unique_id,
        data={CONF_DEVICE_PATH: legacy_unique_id, CONF_DEVICE_NAME: FAKE_DEVICE_NAME},
    )
    legacy.add_to_hass(hass)

    with patch(
        "homeassistant.components.keyboard_remote.config_flow._resolve_yaml_device",
        return_value=(FAKE_DEVICE_PATH, FAKE_DEVICE_NAME, FAKE_BY_ID_BASENAME),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=import_data,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
    assert legacy.unique_id == legacy_unique_id
    assert legacy.data[CONF_DEVICE_PATH] == legacy_unique_id


async def test_import_cannot_identify(hass: HomeAssistant) -> None:
    """Test YAML import aborts when device cannot be identified."""
    with patch(
        "homeassistant.components.keyboard_remote.config_flow._resolve_yaml_device",
        return_value=(None, None, None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_identify_device"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_already_configured(hass: HomeAssistant) -> None:
    """Test YAML import aborts when device is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FAKE_BY_ID_BASENAME,
        data={CONF_DEVICE_PATH: FAKE_DEVICE_PATH},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.keyboard_remote.config_flow._resolve_yaml_device",
        return_value=(FAKE_DEVICE_PATH, FAKE_DEVICE_NAME, FAKE_BY_ID_BASENAME),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={"device_descriptor": FAKE_DEVICE_REAL_PATH},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the options flow allows changing settings."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_KEY_TYPES: ["key_up", "key_down", "key_hold"],
            CONF_EMULATE_KEY_HOLD: True,
            CONF_EMULATE_KEY_HOLD_DELAY: 0.5,
            CONF_EMULATE_KEY_HOLD_REPEAT: 0.05,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_KEY_TYPES: ["key_up", "key_down", "key_hold"],
        CONF_EMULATE_KEY_HOLD: True,
        CONF_EMULATE_KEY_HOLD_DELAY: 0.5,
        CONF_EMULATE_KEY_HOLD_REPEAT: 0.05,
    }


async def test_options_flow_shows_device_path(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the options flow shows the device path in description."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"]["device_path"] == FAKE_DEVICE_PATH


def test_get_device_name_success() -> None:
    """Test _get_device_name returns device name and closes device."""
    mock_dev = MagicMock()
    mock_dev.name = FAKE_DEVICE_NAME

    with (
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.path.realpath",
            return_value=FAKE_DEVICE_REAL_PATH,
        ),
        patch("evdev.InputDevice", return_value=mock_dev),
    ):
        result = _get_device_name(FAKE_DEVICE_PATH)

    assert result == FAKE_DEVICE_NAME
    mock_dev.close.assert_called_once()


def test_get_device_name_oserror() -> None:
    """Test _get_device_name returns None on OSError."""
    with (
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.path.realpath",
            return_value=FAKE_DEVICE_REAL_PATH,
        ),
        patch("evdev.InputDevice", side_effect=OSError("No such device")),
    ):
        result = _get_device_name(FAKE_DEVICE_PATH)

    assert result is None


def test_resolve_yaml_descriptor_with_by_id() -> None:
    """Test resolve with descriptor that has a by-id symlink."""
    by_id_entry = MagicMock(spec_set=os.DirEntry)
    by_id_entry.is_symlink.return_value = True
    by_id_entry.path = FAKE_DEVICE_PATH

    mock_dev = MagicMock()
    mock_dev.name = FAKE_DEVICE_NAME

    with (
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.path.isdir",
            return_value=True,
        ),
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.scandir",
        ) as mock_scandir,
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.path.realpath",
            return_value=FAKE_DEVICE_REAL_PATH,
        ),
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.path.basename",
            return_value=FAKE_BY_ID_BASENAME,
        ),
        patch("evdev.InputDevice", return_value=mock_dev),
    ):
        mock_scandir.return_value.__enter__ = MagicMock(return_value=[by_id_entry])
        mock_scandir.return_value.__exit__ = MagicMock(return_value=False)
        result = _resolve_yaml_device({"device_descriptor": FAKE_DEVICE_REAL_PATH})

    assert result == (FAKE_DEVICE_PATH, FAKE_DEVICE_NAME, FAKE_BY_ID_BASENAME)
    mock_dev.close.assert_called_once()


def test_resolve_yaml_descriptor_no_by_id() -> None:
    """Test resolve with descriptor but no by-id symlink."""
    mock_dev = MagicMock()
    mock_dev.name = FAKE_DEVICE_NAME

    with (
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.path.isdir",
            return_value=False,
        ),
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.path.realpath",
            return_value=FAKE_DEVICE_REAL_PATH,
        ),
        patch("evdev.InputDevice", return_value=mock_dev),
    ):
        result = _resolve_yaml_device({"device_descriptor": FAKE_DEVICE_REAL_PATH})

    assert result == (FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, None)


def test_resolve_yaml_descriptor_oserror() -> None:
    """Test resolve with descriptor when InputDevice raises OSError."""
    with (
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.path.isdir",
            return_value=False,
        ),
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.path.realpath",
            return_value=FAKE_DEVICE_REAL_PATH,
        ),
        patch("evdev.InputDevice", side_effect=OSError("No device")),
    ):
        result = _resolve_yaml_device({"device_descriptor": FAKE_DEVICE_REAL_PATH})

    # Returns descriptor with None name and None unique_id
    assert result == (FAKE_DEVICE_REAL_PATH, None, None)


def test_resolve_yaml_scandir_oserror() -> None:
    """Test resolve continues when scandir on /dev/input/by-id raises OSError."""
    mock_dev = MagicMock()
    mock_dev.name = FAKE_DEVICE_NAME

    with (
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.path.isdir",
            return_value=True,
        ),
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.scandir",
            side_effect=OSError("Permission denied"),
        ),
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.path.realpath",
            return_value=FAKE_DEVICE_REAL_PATH,
        ),
        patch("evdev.InputDevice", return_value=mock_dev),
    ):
        result = _resolve_yaml_device({"device_descriptor": FAKE_DEVICE_REAL_PATH})

    assert result == (FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, None)


def test_resolve_yaml_name_with_by_id() -> None:
    """Test resolve with device name that matches a device with by-id symlink."""
    by_id_entry = MagicMock(spec_set=os.DirEntry)
    by_id_entry.is_symlink.return_value = True
    by_id_entry.path = FAKE_DEVICE_PATH

    mock_dev = MagicMock()
    mock_dev.name = FAKE_DEVICE_NAME

    with (
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.path.isdir",
            return_value=True,
        ),
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.scandir",
        ) as mock_scandir,
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.path.realpath",
            return_value=FAKE_DEVICE_REAL_PATH,
        ),
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.path.basename",
            return_value=FAKE_BY_ID_BASENAME,
        ),
        patch("evdev.InputDevice", return_value=mock_dev),
        patch("evdev.list_devices", return_value=[FAKE_DEVICE_REAL_PATH]),
    ):
        mock_scandir.return_value.__enter__ = MagicMock(return_value=[by_id_entry])
        mock_scandir.return_value.__exit__ = MagicMock(return_value=False)
        result = _resolve_yaml_device({"device_name": FAKE_DEVICE_NAME})

    assert result == (FAKE_DEVICE_PATH, FAKE_DEVICE_NAME, FAKE_BY_ID_BASENAME)


def test_resolve_yaml_name_matching_several_nodes() -> None:
    """Test a name shared by several nodes is not promoted to one by-id path.

    A composite keyboard reports the same name on each node, and picking the
    first would lock the entry to whichever node list_devices returned first.
    """
    by_id_entry = MagicMock(spec_set=os.DirEntry)
    by_id_entry.is_symlink.return_value = True
    by_id_entry.path = FAKE_DEVICE_PATH

    mock_dev = MagicMock()
    mock_dev.name = FAKE_DEVICE_NAME

    with (
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.path.isdir",
            return_value=True,
        ),
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.scandir",
        ) as mock_scandir,
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.path.realpath",
            side_effect=lambda p: {FAKE_DEVICE_PATH: FAKE_DEVICE_REAL_PATH}.get(p, p),
        ),
        patch("evdev.InputDevice", return_value=mock_dev),
        patch(
            "evdev.list_devices",
            return_value=[FAKE_DEVICE_REAL_PATH, "/dev/input/event6"],
        ),
    ):
        mock_scandir.return_value.__enter__ = MagicMock(return_value=[by_id_entry])
        mock_scandir.return_value.__exit__ = MagicMock(return_value=False)
        result = _resolve_yaml_device({"device_name": FAKE_DEVICE_NAME})

    assert result == (None, None, None)


def test_resolve_yaml_name_no_by_id() -> None:
    """Test resolve with device name match but no by-id symlink."""
    mock_dev = MagicMock()
    mock_dev.name = FAKE_DEVICE_NAME

    with (
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.path.isdir",
            return_value=False,
        ),
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.path.realpath",
            return_value=FAKE_DEVICE_REAL_PATH,
        ),
        patch("evdev.InputDevice", return_value=mock_dev),
        patch("evdev.list_devices", return_value=[FAKE_DEVICE_REAL_PATH]),
    ):
        result = _resolve_yaml_device({"device_name": FAKE_DEVICE_NAME})

    assert result == (FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, None)


def test_resolve_yaml_no_match() -> None:
    """Test resolve returns (None, None, None) when nothing matches."""
    with (
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.path.isdir",
            return_value=False,
        ),
        patch("evdev.list_devices", return_value=[]),
    ):
        result = _resolve_yaml_device({"device_name": "Nonexistent Device"})

    assert result == (None, None, None)


def test_resolve_yaml_name_oserror_on_device() -> None:
    """Test resolve with name skips devices that raise OSError."""
    with (
        patch(
            "homeassistant.components.keyboard_remote.config_flow.os.path.isdir",
            return_value=False,
        ),
        patch("evdev.InputDevice", side_effect=OSError("No device")),
        patch("evdev.list_devices", return_value=[FAKE_DEVICE_REAL_PATH]),
    ):
        result = _resolve_yaml_device({"device_name": FAKE_DEVICE_NAME})

    # OSError causes continue, falls through to (None, None, None)
    assert result == (None, None, None)


def test_resolve_yaml_empty_data() -> None:
    """Test resolve with empty data returns (None, None, None)."""
    with patch(
        "homeassistant.components.keyboard_remote.config_flow.os.path.isdir",
        return_value=False,
    ):
        result = _resolve_yaml_device({})

    assert result == (None, None, None)
