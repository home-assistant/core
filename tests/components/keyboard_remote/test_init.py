"""Tests for the Keyboard Remote integration init."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
import errno
from pathlib import PurePath
import threading
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from asyncinotify import Mask
import pytest

from homeassistant.components.keyboard_remote import KeyboardRemoteManager
from homeassistant.components.keyboard_remote.const import (
    CONF_DEVICE_DESCRIPTOR,
    CONF_DEVICE_NAME,
    CONF_DEVICE_PATH,
    CONF_DEVICE_UNIQ,
    CONF_EMULATE_KEY_HOLD,
    CONF_EMULATE_KEY_HOLD_DELAY,
    CONF_EMULATE_KEY_HOLD_REPEAT,
    CONF_KEY_TYPES,
    DEFAULT_EMULATE_KEY_HOLD,
    DEFAULT_EMULATE_KEY_HOLD_DELAY,
    DEFAULT_EMULATE_KEY_HOLD_REPEAT,
    DEFAULT_KEY_TYPES,
    DEVINPUT,
    DEVINPUT_BY_ID,
    DOMAIN,
    EVENT_KEYBOARD_REMOTE_COMMAND_RECEIVED,
    EVENT_KEYBOARD_REMOTE_CONNECTED,
    EVENT_KEYBOARD_REMOTE_DISCONNECTED,
    KEY_CODE,
    KEY_VALUE,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER, ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    CoreState,
    Event,
    HomeAssistant,
    callback,
)
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import (
    EV_REL,
    FAKE_DEVICE_NAME,
    FAKE_DEVICE_PATH,
    FAKE_DEVICE_PATH_2,
    FAKE_DEVICE_REAL_PATH,
    FakeInput,
)

from tests.common import MockConfigEntry, async_capture_events, async_fire_time_changed

REMOTE_PATH = "/dev/input/event7"
REMOTE_NAME = "BT Remote"
OTHER_LINK = "/dev/input/by-id/usb-Other-event-kbd"

OPTIONS = {
    CONF_KEY_TYPES: DEFAULT_KEY_TYPES,
    CONF_EMULATE_KEY_HOLD: DEFAULT_EMULATE_KEY_HOLD,
    CONF_EMULATE_KEY_HOLD_DELAY: DEFAULT_EMULATE_KEY_HOLD_DELAY,
    CONF_EMULATE_KEY_HOLD_REPEAT: DEFAULT_EMULATE_KEY_HOLD_REPEAT,
}


def _entry(
    data: dict[str, str],
    *,
    source: str = SOURCE_USER,
    unique_id: str | None = None,
    **options: Any,
) -> MockConfigEntry:
    """Create an entry with the default options, overridden by options."""
    return MockConfigEntry(
        domain=DOMAIN,
        source=source,
        unique_id=unique_id or data.get(CONF_DEVICE_PATH) or data[CONF_DEVICE_NAME],
        title=data.get(CONF_DEVICE_NAME, "Keyboard"),
        data=data,
        options={**OPTIONS, **options},
    )


def _remote_entry(**options: Any) -> MockConfigEntry:
    """Create an entry matched by name, as for a Bluetooth remote."""
    return _entry({CONF_DEVICE_NAME: REMOTE_NAME}, **options)


async def _set_up(
    hass: HomeAssistant, fake_input: FakeInput, entry: MockConfigEntry
) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await fake_input.settle()


def _connected(descriptor: str, name: str = FAKE_DEVICE_NAME) -> dict[str, str]:
    return {CONF_DEVICE_DESCRIPTOR: descriptor, CONF_DEVICE_NAME: name}


@pytest.mark.parametrize(
    "existing",
    [
        pytest.param([], id="new_entry"),
        pytest.param(
            [
                MockConfigEntry(
                    domain=DOMAIN,
                    source=SOURCE_IMPORT,
                    unique_id="usb-Test_Keyboard-event-kbd",
                    data={
                        CONF_DEVICE_PATH: FAKE_DEVICE_PATH,
                        CONF_DEVICE_NAME: FAKE_DEVICE_NAME,
                        CONF_DEVICE_DESCRIPTOR: FAKE_DEVICE_REAL_PATH,
                    },
                    options=OPTIONS,
                )
            ],
            id="already_imported",
        ),
    ],
)
async def test_yaml_import_creates_entry_and_deprecation_issue(
    hass: HomeAssistant,
    fake_input: FakeInput,
    issue_registry: ir.IssueRegistry,
    existing: list[MockConfigEntry],
) -> None:
    """Test a YAML device is imported once and YAML is flagged deprecated.

    After the first start the import finds its entry, which must still flag
    the YAML as deprecated.
    """
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    for entry in existing:
        entry.add_to_hass(hass)

    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"device_descriptor": FAKE_DEVICE_REAL_PATH}}
    )
    await fake_input.settle()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert [entry.data[CONF_DEVICE_PATH] for entry in entries] == [FAKE_DEVICE_PATH]
    assert set(issue_registry.issues) == {
        (HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}")
    }


async def test_async_setup_no_yaml_config(hass: HomeAssistant) -> None:
    """Test setup without YAML configuration starts no import."""
    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    mock_init.assert_not_called()


async def test_async_setup_imports_each_normalized_block(hass: HomeAssistant) -> None:
    """Test each YAML block is imported with coerced values and defaults."""
    with patch.object(
        hass.config_entries.flow,
        "async_init",
        return_value={"type": FlowResultType.ABORT, "reason": "already_configured"},
    ) as mock_init:
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: [
                    {"device_descriptor": FAKE_DEVICE_REAL_PATH},
                    {
                        "device_name": "Keyboard",
                        "type": "key_down",
                        "emulate_key_hold_delay": 1,
                    },
                ]
            },
        )
        await hass.async_block_till_done()

    defaults = {
        "type": ["key_up"],
        "emulate_key_hold": False,
        "emulate_key_hold_delay": 0.25,
        "emulate_key_hold_repeat": 0.033,
    }
    assert [init.kwargs["data"] for init in mock_init.call_args_list] == [
        {"device_descriptor": FAKE_DEVICE_REAL_PATH, **defaults},
        {
            **defaults,
            "device_name": "Keyboard",
            "type": ["key_down"],
            "emulate_key_hold_delay": 1.0,
        },
    ]


async def test_async_setup_accepts_values_the_import_fits(
    hass: HomeAssistant,
) -> None:
    """Test YAML with unknown keys or odd numbers still imports.

    An invalid config would keep every entry of the integration from loading,
    so values the import can fit into the options are accepted.
    """
    with patch.object(
        hass.config_entries.flow,
        "async_init",
        return_value={"type": FlowResultType.ABORT, "reason": "already_configured"},
    ) as mock_init:
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    "device_descriptor": FAKE_DEVICE_REAL_PATH,
                    "emulate_key_hold_dealy": 1,
                    "type": [],
                    "emulate_key_hold_delay": -1,
                    "emulate_key_hold_repeat": "0.5",
                }
            },
        )
        await hass.async_block_till_done()

    [init] = mock_init.call_args_list
    assert init.kwargs["data"] == {
        "device_descriptor": FAKE_DEVICE_REAL_PATH,
        "emulate_key_hold_dealy": 1,
        "type": [],
        "emulate_key_hold": False,
        "emulate_key_hold_delay": -1.0,
        "emulate_key_hold_repeat": 0.5,
    }


@pytest.mark.parametrize(
    "device_block",
    [
        pytest.param(
            {"device_descriptor": "/dev/input/event5", "type": "bogus"},
            id="unknown_key_type",
        ),
        pytest.param(
            {"device_descriptor": "/dev/input/event5", "device_name": "Keyboard"},
            id="descriptor_and_name",
        ),
        pytest.param(
            {"device_descriptor": "/dev/input/event5", "emulate_key_hold_delay": "a"},
            id="delay_not_a_number",
        ),
        pytest.param({"type": "key_up"}, id="no_device"),
        pytest.param({"device_descriptor": ""}, id="empty_descriptor"),
    ],
)
async def test_async_setup_rejects_invalid_yaml(
    hass: HomeAssistant,
    device_block: dict[str, str],
) -> None:
    """Test a YAML block that cannot be used fails setup instead of importing.

    An unknown key type would crash the monitor on the first key press.
    """
    with patch.object(hass.config_entries.flow, "async_init") as mock_init:
        assert not await async_setup_component(hass, DOMAIN, {DOMAIN: device_block})
        await hass.async_block_till_done()

    mock_init.assert_not_called()


@pytest.mark.parametrize(
    ("inotify_error", "watch_errors", "expected_closed"),
    [
        pytest.param(
            OSError(errno.EMFILE, "Too many open files"),
            {},
            [],
            id="inotify_instances_exhausted",
        ),
        pytest.param(
            None,
            {DEVINPUT: FileNotFoundError(errno.ENOENT, "No such file")},
            [True],
            id="input_directory_missing",
        ),
    ],
)
async def test_setup_retries_when_devices_cannot_be_watched(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
    inotify_error: OSError | None,
    watch_errors: dict[str, OSError],
    expected_closed: list[bool],
) -> None:
    """Test setup is retried, instead of loading an entry that cannot work.

    A container without /dev/input mapped, or a host out of inotify instances,
    cannot be watched. Nothing is left behind for the retry.
    """
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    fake_input.inotify_error = inotify_error
    fake_input.watch_errors = watch_errors
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await fake_input.settle()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert [
        inotify.closed for inotify in fake_input.inotify_instances
    ] == expected_closed

    fake_input.inotify_error = None
    fake_input.watch_errors = {}
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await fake_input.settle()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_by_id_watch_failure_at_setup_is_retried(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a by-id watch that fails at setup does not fail setup.

    Devices without a by-id link do not need it, and the watch is retried on
    later device events, so a by-id device plugged in once it works connects.
    """
    fake_input.add("/dev/input/event2", "Other", link=OTHER_LINK)
    fake_input.watch_errors[DEVINPUT_BY_ID] = OSError(errno.ENOSPC, "No space")

    await _set_up(hass, fake_input, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert "Unable to watch /dev/input/by-id" in caplog.text

    fake_input.watch_errors.clear()
    kbd = await fake_input.plug(
        FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH
    )

    kbd.grab.assert_called_once()


async def test_devices_connect_once_home_assistant_started(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test devices are only grabbed once Home Assistant has started."""
    hass.set_state(CoreState.not_running)
    kbd = fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    await _set_up(hass, fake_input, mock_config_entry)

    kbd.grab.assert_not_called()

    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await fake_input.settle()

    kbd.grab.assert_called_once()


async def test_unload_before_start_closes_watcher(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an entry unloaded before Home Assistant started closes the watcher.

    The watcher opens at setup, but devices are only scanned once Home
    Assistant is running.
    """
    hass.set_state(CoreState.not_running)
    await _set_up(hass, fake_input, mock_config_entry)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await fake_input.settle()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert fake_input.inotify is not None
    assert fake_input.inotify.closed


@pytest.mark.parametrize(
    ("entry", "devices", "expected_grabbed", "expected_closed"),
    [
        pytest.param(
            _entry({CONF_DEVICE_PATH: FAKE_DEVICE_PATH, CONF_DEVICE_NAME: "Keyboard"}),
            [(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, FAKE_DEVICE_PATH)],
            [FAKE_DEVICE_REAL_PATH],
            [],
            id="by_path",
        ),
        pytest.param(
            _remote_entry(),
            [(REMOTE_PATH, REMOTE_NAME, None)],
            [REMOTE_PATH],
            [],
            id="by_name",
        ),
        # A composite keyboard reports the same name on each node, and only the
        # node the user picked carries the configured link.
        pytest.param(
            _entry(
                {CONF_DEVICE_PATH: FAKE_DEVICE_PATH, CONF_DEVICE_NAME: FAKE_DEVICE_NAME}
            ),
            [
                ("/dev/input/event4", FAKE_DEVICE_NAME, None),
                (FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, FAKE_DEVICE_PATH),
            ],
            [FAKE_DEVICE_REAL_PATH],
            ["/dev/input/event4"],
            id="path_over_same_named_sibling",
        ),
        pytest.param(
            _entry(
                {CONF_DEVICE_PATH: FAKE_DEVICE_PATH, CONF_DEVICE_NAME: FAKE_DEVICE_NAME}
            ),
            [("/dev/input/event9", FAKE_DEVICE_NAME, None)],
            [],
            ["/dev/input/event9"],
            id="path_entry_ignores_name_while_link_missing",
        ),
        # The node the old YAML named may since belong to an unrelated device
        pytest.param(
            _entry(
                {
                    CONF_DEVICE_PATH: FAKE_DEVICE_PATH,
                    CONF_DEVICE_NAME: FAKE_DEVICE_NAME,
                    CONF_DEVICE_DESCRIPTOR: "/dev/input/event3",
                },
                source=SOURCE_IMPORT,
            ),
            [("/dev/input/event3", "Mouse", None)],
            [],
            ["/dev/input/event3"],
            id="reused_yaml_descriptor",
        ),
        pytest.param(
            _remote_entry(),
            [("/dev/input/event8", "Mouse", None)],
            [],
            ["/dev/input/event8"],
            id="unrelated_device",
        ),
    ],
)
async def test_startup_connects_matching_device(
    hass: HomeAssistant,
    fake_input: FakeInput,
    entry: MockConfigEntry,
    devices: list[tuple[str, str, str | None]],
    expected_grabbed: list[str],
    expected_closed: list[str],
) -> None:
    """Test the startup scan grabs the device the entry identifies, and only it.

    Nodes that cannot be opened are skipped.
    """
    fake_input.add_unopenable("/dev/input/event1")
    added = {
        path: fake_input.add(path, name, link=link) for path, name, link in devices
    }

    await _set_up(hass, fake_input, entry)

    assert {path: dev.grab.called for path, dev in added.items()} == {
        path: path in expected_grabbed for path in added
    }
    assert {path: dev.close.called for path, dev in added.items()} == {
        path: path in expected_closed for path in added
    }


async def test_bluetooth_remote_matched_by_address(
    hass: HomeAssistant,
    fake_input: FakeInput,
) -> None:
    """Test an entry with a uniq connects only the remote with that address.

    Identical remotes report the same name, and only their Bluetooth address,
    reported as the evdev uniq, tells them apart.
    """
    first = fake_input.add(REMOTE_PATH, REMOTE_NAME, uniq="aa:bb:cc:dd:ee:01")
    await _set_up(
        hass,
        fake_input,
        _entry(
            {CONF_DEVICE_NAME: REMOTE_NAME, CONF_DEVICE_UNIQ: "aa:bb:cc:dd:ee:02"},
            unique_id="aa:bb:cc:dd:ee:02 BT Remote",
        ),
    )

    second = await fake_input.plug(
        "/dev/input/event8", REMOTE_NAME, uniq="aa:bb:cc:dd:ee:02"
    )

    first.grab.assert_not_called()
    second.grab.assert_called_once()


@pytest.mark.parametrize(
    ("entry", "expected_descriptor"),
    [
        pytest.param(
            _entry(
                {
                    CONF_DEVICE_PATH: FAKE_DEVICE_PATH,
                    CONF_DEVICE_NAME: FAKE_DEVICE_NAME,
                    CONF_DEVICE_DESCRIPTOR: "/dev/input/event3",
                },
                source=SOURCE_IMPORT,
            ),
            "/dev/input/event3",
            id="yaml_descriptor",
        ),
        pytest.param(
            _entry(
                {
                    CONF_DEVICE_PATH: FAKE_DEVICE_PATH,
                    CONF_DEVICE_NAME: FAKE_DEVICE_NAME,
                },
                source=SOURCE_IMPORT,
            ),
            FAKE_DEVICE_REAL_PATH,
            id="yaml_name",
        ),
        pytest.param(
            _entry(
                {CONF_DEVICE_PATH: FAKE_DEVICE_PATH, CONF_DEVICE_NAME: FAKE_DEVICE_NAME}
            ),
            FAKE_DEVICE_PATH,
            id="ui",
        ),
    ],
)
async def test_events_report_the_pre_migration_descriptor(
    hass: HomeAssistant,
    fake_input: FakeInput,
    entry: MockConfigEntry,
    expected_descriptor: str,
) -> None:
    """Test events report what the integration reported before the migration.

    Automations written against the YAML setup must keep matching, even though
    the import also resolved a stable by-id path. YAML configured by name
    reported the opened node, and UI entries report their by-id path.
    """
    kbd = fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    connected = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_CONNECTED)
    commands = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_COMMAND_RECEIVED)
    await _set_up(hass, fake_input, entry)

    await fake_input.press(kbd, 30, KEY_VALUE["key_up"])

    assert [e.data for e in connected] == [_connected(expected_descriptor)]
    assert [e.data[CONF_DEVICE_DESCRIPTOR] for e in commands] == [expected_descriptor]


async def test_plugged_device_connects(
    hass: HomeAssistant,
    fake_input: FakeInput,
) -> None:
    """Test a device without a by-id link connects when plugged in."""
    connected = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_CONNECTED)
    await _set_up(hass, fake_input, _remote_entry())

    remote = await fake_input.plug(REMOTE_PATH, REMOTE_NAME)

    remote.grab.assert_called_once()
    assert [e.data for e in connected] == [_connected(REMOTE_PATH, REMOTE_NAME)]


@pytest.mark.parametrize(
    "other_links",
    [
        pytest.param({}, id="first_link_creates_directory"),
        pytest.param({OTHER_LINK: "/dev/input/event2"}, id="link_renamed_into_place"),
    ],
)
async def test_plugged_device_connects_through_late_link(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
    other_links: dict[str, str],
) -> None:
    """Test a by-id entry connects when its link appears after the node's events.

    udev adds the link only after the node's CREATE and ATTRIB, which cannot
    match an entry configured with the link. The link itself arrives by the
    by-id directory being created with it, or by a rename into place.
    """
    for link, target in other_links.items():
        fake_input.add(target, "Other", link=link)
    connected = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_CONNECTED)
    await _set_up(hass, fake_input, mock_config_entry)

    kbd = await fake_input.plug(
        FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH
    )

    kbd.grab.assert_called_once()
    assert [e.data for e in connected] == [_connected(FAKE_DEVICE_PATH)]


async def test_by_id_watch_failure_still_connects(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a by-id directory that cannot be watched does not stop monitoring.

    Waiting entries are still rechecked when the directory appears, since its
    first link is already in it. The watch is retried on later device events,
    so a by-id device plugged in once it can be added still connects through
    its late link.
    """
    await _set_up(hass, fake_input, mock_config_entry)
    await _set_up(
        hass,
        fake_input,
        _entry({CONF_DEVICE_PATH: FAKE_DEVICE_PATH_2, CONF_DEVICE_NAME: "Remote"}),
    )
    fake_input.watch_errors[DEVINPUT_BY_ID] = OSError(errno.ENOSPC, "No space")

    kbd = await fake_input.plug(
        FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH
    )

    assert "Unable to watch /dev/input/by-id" in caplog.text
    kbd.grab.assert_called_once()

    fake_input.watch_errors.clear()
    remote = await fake_input.plug(
        "/dev/input/event6", "Remote", link=FAKE_DEVICE_PATH_2
    )

    remote.grab.assert_called_once()


async def test_unload_releases_devices_after_the_watcher_failed(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test unloading still releases devices when reading inotify had failed.

    Re-raising the watcher's error there would skip releasing the devices and
    closing inotify, and fail the unload.
    """
    kbd = fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    await _set_up(hass, fake_input, mock_config_entry)
    assert fake_input.inotify is not None
    fake_input.inotify.queue.put_nowait(OSError(errno.EIO, "Input/output error"))
    await fake_input.settle()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await fake_input.settle()

    assert "The input device watcher had failed" in caplog.text
    kbd.close.assert_called_once()
    assert fake_input.inotify.closed


async def test_watcher_survives_an_event_it_cannot_handle(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an error handling one event does not end device monitoring.

    Otherwise no device would connect again, and the error would only surface
    when unloading, where it would skip releasing the devices.
    """
    await _set_up(hass, fake_input, mock_config_entry)
    assert fake_input.inotify is not None
    # An event without a mask makes the handler raise
    fake_input.inotify.queue.put_nowait(
        SimpleNamespace(name=PurePath("event9"), watch=None)
    )
    await fake_input.settle()

    kbd = await fake_input.plug(
        FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH
    )

    assert "Error handling input device event" in caplog.text
    kbd.grab.assert_called_once()
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("target", "expected_opened"),
    [
        pytest.param("/dev/input/mouse0", False, id="not_an_event_node"),
        pytest.param("/dev/input/event8", True, id="no_matching_entry"),
    ],
)
async def test_by_id_link_without_matching_device(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
    target: str,
    expected_opened: bool,
) -> None:
    """Test a new link that leads to no configured device starts nothing.

    Links to nodes evdev cannot open, like mouse nodes, are not even opened.
    """
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    mouse = fake_input.add("/dev/input/event8", "Mouse")
    connected = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_CONNECTED)
    await _set_up(hass, fake_input, mock_config_entry)
    fake_input.opened.clear()

    await fake_input.link("/dev/input/by-id/usb-Mouse-event-mouse", target)

    assert (target in fake_input.opened) is expected_opened
    mouse.grab.assert_not_called()
    assert len(connected) == 1


async def test_unrelated_device_is_not_grabbed(
    hass: HomeAssistant,
    fake_input: FakeInput,
) -> None:
    """Test a plugged device that no entry identifies is released again."""
    await _set_up(hass, fake_input, _remote_entry())

    mouse = await fake_input.plug("/dev/input/event8", "Mouse")

    mouse.grab.assert_not_called()
    mouse.close.assert_called()


async def test_unplug_and_replug(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a device is released when unplugged and connects again when replugged.

    Unplugging the last device also removes the by-id directory, which udev
    creates again with the link when the device comes back.
    """
    kbd = fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    connected = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_CONNECTED)
    disconnected = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_DISCONNECTED)
    await _set_up(hass, fake_input, mock_config_entry)

    await fake_input.unplug(FAKE_DEVICE_REAL_PATH)

    kbd.close.assert_called_once()
    assert [e.data for e in disconnected] == [_connected(FAKE_DEVICE_PATH)]

    replugged = await fake_input.plug(
        FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH
    )

    replugged.grab.assert_called_once()
    assert len(connected) == 2


async def test_second_node_does_not_replace_connected_device(
    hass: HomeAssistant,
    fake_input: FakeInput,
) -> None:
    """Test a same-named node is left alone while the entry has a device.

    Mapping it to the entry would let unplugging it stop the device the entry
    is really reading from.
    """
    remote = fake_input.add(REMOTE_PATH, REMOTE_NAME)
    connected = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_CONNECTED)
    disconnected = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_DISCONNECTED)
    await _set_up(hass, fake_input, _remote_entry())

    await fake_input.touch(REMOTE_PATH)
    sibling = await fake_input.plug("/dev/input/event8", REMOTE_NAME)
    await fake_input.unplug("/dev/input/event8")

    sibling.grab.assert_not_called()
    remote.close.assert_not_called()
    assert len(connected) == 1
    assert not disconnected


async def test_entry_added_later_connects_present_device(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an entry added after startup connects a device already present."""
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    remote = fake_input.add(REMOTE_PATH, REMOTE_NAME)
    await _set_up(hass, fake_input, mock_config_entry)

    await _set_up(hass, fake_input, _remote_entry())

    remote.grab.assert_called_once()


async def test_entry_added_later_leaves_claimed_node_alone(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a later entry does not take a node another entry already reads."""
    kbd = fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    connected = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_CONNECTED)
    await _set_up(hass, fake_input, mock_config_entry)

    await _set_up(
        hass,
        fake_input,
        _entry({CONF_DEVICE_NAME: FAKE_DEVICE_NAME}, unique_id="by-name"),
    )

    kbd.grab.assert_called_once()
    assert len(connected) == 1


@pytest.mark.parametrize(
    ("key_types", "expected"),
    [
        pytest.param(["key_up"], [(30, "key_up")], id="default_key_up"),
        pytest.param(
            ["key_down", "key_hold"],
            [(30, "key_down"), (30, "key_hold")],
            id="down_and_hold",
        ),
    ],
)
async def test_key_events(
    hass: HomeAssistant,
    fake_input: FakeInput,
    key_types: list[str],
    expected: list[tuple[int, str]],
) -> None:
    """Test configured key events fire commands, and other input is ignored."""
    kbd = fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    commands = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_COMMAND_RECEIVED)
    await _set_up(
        hass,
        fake_input,
        _entry(
            {CONF_DEVICE_PATH: FAKE_DEVICE_PATH, CONF_DEVICE_NAME: FAKE_DEVICE_NAME},
            **{CONF_KEY_TYPES: key_types},
        ),
    )

    await fake_input.press(kbd, 30, KEY_VALUE["key_down"])
    await fake_input.press(kbd, 30, KEY_VALUE["key_hold"])
    await fake_input.press(kbd, 30, KEY_VALUE["key_up"])
    # A relative event with a value that is also a key value
    await fake_input.send(kbd, SimpleNamespace(type=EV_REL, code=0, value=1))

    assert [(e.data[KEY_CODE], e.data["type"]) for e in commands] == expected
    assert {
        (e.data[CONF_DEVICE_DESCRIPTOR], e.data[CONF_DEVICE_NAME]) for e in commands
    } == {(FAKE_DEVICE_PATH, FAKE_DEVICE_NAME)}


async def _advance(hass: HomeAssistant, seconds: float) -> None:
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done()


async def test_key_hold_emulation(
    hass: HomeAssistant,
    fake_input: FakeInput,
) -> None:
    """Test a held key repeats key_hold after the delay until it is released."""
    kbd = fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    commands = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_COMMAND_RECEIVED)
    await _set_up(
        hass,
        fake_input,
        _entry(
            {CONF_DEVICE_PATH: FAKE_DEVICE_PATH, CONF_DEVICE_NAME: FAKE_DEVICE_NAME},
            **{
                CONF_KEY_TYPES: ["key_down"],
                CONF_EMULATE_KEY_HOLD: True,
                CONF_EMULATE_KEY_HOLD_DELAY: 1.0,
                CONF_EMULATE_KEY_HOLD_REPEAT: 0.5,
            },
        ),
    )

    # Each step fires only the timers already scheduled, so one repeat each
    await fake_input.press(kbd, 30, KEY_VALUE["key_down"])
    await _advance(hass, 60)
    await _advance(hass, 60)
    await fake_input.press(kbd, 30, KEY_VALUE["key_up"])
    await _advance(hass, 60)

    assert [e.data["type"] for e in commands] == ["key_down", "key_hold", "key_hold"]
    assert {e.data[CONF_DEVICE_DESCRIPTOR] for e in commands} == {FAKE_DEVICE_PATH}


async def test_unplug_stops_key_hold(
    hass: HomeAssistant,
    fake_input: FakeInput,
) -> None:
    """Test a key held while the device is unplugged stops repeating."""
    kbd = fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    commands = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_COMMAND_RECEIVED)
    await _set_up(
        hass,
        fake_input,
        _entry(
            {CONF_DEVICE_PATH: FAKE_DEVICE_PATH, CONF_DEVICE_NAME: FAKE_DEVICE_NAME},
            **{CONF_EMULATE_KEY_HOLD: True, CONF_EMULATE_KEY_HOLD_DELAY: 1.0},
        ),
    )

    await fake_input.press(kbd, 30, KEY_VALUE["key_down"])
    await fake_input.unplug(FAKE_DEVICE_REAL_PATH)
    await _advance(hass, 60)

    assert commands == []


async def test_unexpected_read_error_releases_device(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an unexpected error while reading releases the device.

    Otherwise the device stays grabbed, the entry looks busy so the device
    cannot connect again, and unloading the entry fails.
    """
    kbd = fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    disconnected = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_DISCONNECTED)
    await _set_up(hass, fake_input, mock_config_entry)

    await fake_input.send(kbd, ValueError("unexpected"))

    assert "Unexpected error reading Test Keyboard" in caplog.text
    kbd.close.assert_called_once()
    assert len(disconnected) == 1

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_grab_failure_warns_and_releases(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a device held by another program is reported and released."""
    kbd = fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    kbd.grab.side_effect = OSError(errno.EBUSY, "Device or resource busy")
    disconnected = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_DISCONNECTED)

    await _set_up(hass, fake_input, mock_config_entry)

    assert "Unable to grab Test Keyboard, it may be in use by another program" in (
        caplog.text
    )
    kbd.close.assert_called_once()
    assert len(disconnected) == 1


async def _stop_home_assistant(
    hass: HomeAssistant, fake_input: FakeInput, entry: MockConfigEntry
) -> None:
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await fake_input.settle(wait_for_executor=False)


async def _unload(
    hass: HomeAssistant, fake_input: FakeInput, entry: MockConfigEntry
) -> None:
    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    "stop",
    [
        pytest.param(_stop_home_assistant, id="home_assistant_stop"),
        pytest.param(_unload, id="unload"),
    ],
)
async def test_stop_releases_devices(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
    stop: Callable[[HomeAssistant, FakeInput, MockConfigEntry], Awaitable[None]],
) -> None:
    """Test devices are ungrabbed and the watcher closed when stopping.

    Config entries are not unloaded when Home Assistant stops, so stopping
    has to release the devices itself.
    """
    kbd = fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    disconnected = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_DISCONNECTED)
    await _set_up(hass, fake_input, mock_config_entry)

    await stop(hass, fake_input, mock_config_entry)
    await fake_input.settle()

    kbd.ungrab.assert_called_once()
    kbd.close.assert_called_once()
    assert len(disconnected) == 1
    assert fake_input.inotify is not None
    assert fake_input.inotify.closed


def _drop_input_directory_watch(fake_input: FakeInput, kbd: MagicMock) -> None:
    fake_input.rm_watch_errors[DEVINPUT] = OSError(errno.EINVAL, "Invalid argument")


def _drop_by_id_watch(fake_input: FakeInput, kbd: MagicMock) -> None:
    fake_input.rm_watch_errors[DEVINPUT_BY_ID] = OSError(
        errno.EINVAL, "Invalid argument"
    )


def _fail_ungrab(fake_input: FakeInput, kbd: MagicMock) -> None:
    kbd.ungrab.side_effect = OSError(errno.ENODEV, "No such device")


@pytest.mark.parametrize(
    "fail",
    [
        # The kernel drops a watch when its directory goes away, and removing
        # it again raises
        pytest.param(_drop_input_directory_watch, id="input_directory_watch_gone"),
        pytest.param(_drop_by_id_watch, id="by_id_directory_watch_gone"),
        pytest.param(_fail_ungrab, id="ungrab_fails"),
    ],
)
async def test_unload_releases_devices_despite_errors(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
    fail: Callable[[FakeInput, MagicMock], None],
) -> None:
    """Test unloading still closes the device when parts of the teardown fail."""
    kbd = fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    await _set_up(hass, fake_input, mock_config_entry)
    fail(fake_input, kbd)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await fake_input.settle()

    kbd.close.assert_called_once()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_unload_one_entry_keeps_the_other_device(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading one entry releases only its own device."""
    kbd = fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    remote = fake_input.add(REMOTE_PATH, REMOTE_NAME)
    await _set_up(hass, fake_input, mock_config_entry)
    await _set_up(hass, fake_input, _remote_entry())

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await fake_input.settle()

    kbd.ungrab.assert_called_once()
    remote.ungrab.assert_not_called()

    remote_commands = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_COMMAND_RECEIVED)
    await fake_input.press(remote, 30, KEY_VALUE["key_up"])

    assert len(remote_commands) == 1


async def test_entry_set_up_during_last_unload_gets_new_manager(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an entry that sets up while the last one unloads still works.

    Registering with the manager being stopped would leave it loaded but
    unable to connect its device.
    """
    await _set_up(hass, fake_input, mock_config_entry)
    remote_entry = _remote_entry()
    remote_entry.add_to_hass(hass)
    stop = KeyboardRemoteManager.async_stop

    async def _set_up_other_entry_during_stop(manager: KeyboardRemoteManager) -> None:
        await hass.config_entries.async_setup(remote_entry.entry_id)
        await stop(manager)

    with patch.object(
        KeyboardRemoteManager,
        "async_stop",
        autospec=True,
        side_effect=_set_up_other_entry_during_stop,
    ):
        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await fake_input.settle()

    assert remote_entry.state is ConfigEntryState.LOADED
    remote = await fake_input.plug(REMOTE_PATH, REMOTE_NAME)
    remote.grab.assert_called_once()


def _next_event(hass: HomeAssistant, event_type: str) -> asyncio.Future[Any]:
    """Return a future resolved by the next event of this type."""
    future: asyncio.Future[Any] = hass.loop.create_future()

    @callback
    def _resolve(event: Event) -> None:
        future.set_result(event)

    hass.bus.async_listen_once(event_type, _resolve)
    return future


async def _wait_in_executor(hass: HomeAssistant, event: threading.Event) -> None:
    assert await hass.async_add_executor_job(event.wait, 5)


async def test_read_failure_during_unplug_teardown(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a read failure while the DELETE teardown ungrabs releases once.

    A second teardown would pass remove_reader the closed fd of -1, which
    raises and ends the watcher, so nothing would connect again.
    """
    kbd = fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    disconnected = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_DISCONNECTED)
    await _set_up(hass, fake_input, mock_config_entry)
    ungrabbing, release = kbd.ungrab.hold()
    released = _next_event(hass, EVENT_KEYBOARD_REMOTE_DISCONNECTED)

    fake_input.remove_node(FAKE_DEVICE_REAL_PATH)
    await _wait_in_executor(hass, ungrabbing)
    await fake_input.send(
        kbd, OSError(errno.ENODEV, "No such device"), wait_for_executor=False
    )
    release.set()
    await asyncio.wait_for(released, 5)
    await fake_input.settle()

    kbd.close.assert_called_once()
    assert len(disconnected) == 1

    replugged = await fake_input.plug(
        FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH
    )
    replugged.grab.assert_called_once()


async def test_device_found_during_teardown_stays_connected(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a node found while the entry's old node ungrabs stays connected.

    The entry is free once its teardown starts, so a device check finishing
    meanwhile can start it on another node before the teardown ends.
    """
    await _set_up(hass, fake_input, mock_config_entry)
    listing, release_listing = fake_input.hold_listing()
    remote_entry = _remote_entry()
    remote_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(remote_entry.entry_id)
    await _wait_in_executor(hass, listing)
    old = fake_input.add("/dev/input/event9", REMOTE_NAME)
    await fake_input.touch("/dev/input/event9", wait_for_executor=False)
    await fake_input.wait_until(lambda: old.grab.called)
    ungrabbing, release_ungrab = old.ungrab.hold()
    remote = fake_input.add(REMOTE_PATH, REMOTE_NAME)

    fake_input.remove_node("/dev/input/event9")
    await _wait_in_executor(hass, ungrabbing)
    release_listing.set()
    await fake_input.wait_until(lambda: remote.grab.called)
    release_ungrab.set()
    await fake_input.settle()

    assert await hass.config_entries.async_unload(remote_entry.entry_id)
    await fake_input.settle()
    remote.ungrab.assert_called_once()
    remote.close.assert_called_once()


async def test_entry_registered_during_startup_scan_connects(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an entry that loads while the startup scan runs still connects.

    The scan works from the entries registered when it started, so an entry
    registering while it runs is checked once the scan is done.
    """
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    remote = fake_input.add(REMOTE_PATH, REMOTE_NAME)
    listing, release = fake_input.hold_listing()
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await _wait_in_executor(hass, listing)
    # Added only now, as setting up the domain would load it with the first
    remote_entry = _remote_entry()
    remote_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(remote_entry.entry_id)
    release.set()
    await fake_input.settle()

    remote.grab.assert_called_once()


@pytest.mark.parametrize(
    "stop",
    [
        # Entries stay registered when Home Assistant stops, so only the
        # manager stopping keeps the check from claiming the device
        pytest.param(_stop_home_assistant, id="home_assistant_stop"),
        pytest.param(_unload, id="entry_unloaded"),
    ],
)
async def test_device_check_finishing_after_stop_grabs_nothing(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
    stop: Callable[[HomeAssistant, FakeInput, MockConfigEntry], Awaitable[None]],
) -> None:
    """Test a device check still scanning when its entry stops grabs nothing.

    Device checks run untracked, so one can find its device after the entry
    or the whole manager has stopped.
    """
    await _set_up(hass, fake_input, mock_config_entry)
    remote = fake_input.add(REMOTE_PATH, REMOTE_NAME)
    listing, release = fake_input.hold_listing()
    remote_entry = _remote_entry()
    remote_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(remote_entry.entry_id)
    await _wait_in_executor(hass, listing)
    await stop(hass, fake_input, remote_entry)
    release.set()
    await fake_input.settle()

    remote.grab.assert_not_called()
    remote.close.assert_called()


async def test_key_down_without_emulation_does_not_repeat(
    hass: HomeAssistant,
    fake_input: FakeInput,
) -> None:
    """Test a held key fires no key_hold events unless emulation is enabled."""
    kbd = fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    commands = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_COMMAND_RECEIVED)
    await _set_up(
        hass,
        fake_input,
        _entry(
            {CONF_DEVICE_PATH: FAKE_DEVICE_PATH, CONF_DEVICE_NAME: FAKE_DEVICE_NAME},
            **{CONF_KEY_TYPES: ["key_hold"]},
        ),
    )

    await fake_input.press(kbd, 30, KEY_VALUE["key_down"])
    await _advance(hass, 60)

    assert commands == []


async def test_repeated_key_down_keeps_one_repeat(
    hass: HomeAssistant,
    fake_input: FakeInput,
) -> None:
    """Test a second key_down for a held key replaces its repeat.

    A key_up lost while the loop stalled would otherwise leave the first
    repeat firing key_hold forever.
    """
    kbd = fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    commands = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_COMMAND_RECEIVED)
    await _set_up(
        hass,
        fake_input,
        _entry(
            {CONF_DEVICE_PATH: FAKE_DEVICE_PATH, CONF_DEVICE_NAME: FAKE_DEVICE_NAME},
            **{CONF_EMULATE_KEY_HOLD: True, CONF_EMULATE_KEY_HOLD_DELAY: 1.0},
        ),
    )

    await fake_input.press(kbd, 30, KEY_VALUE["key_down"])
    await fake_input.press(kbd, 30, KEY_VALUE["key_down"])
    await fake_input.press(kbd, 30, KEY_VALUE["key_up"])
    await _advance(hass, 60)
    await _advance(hass, 60)

    assert [e.data["type"] for e in commands] == ["key_up"]


async def test_unload_while_key_held_stops_repeating(
    hass: HomeAssistant,
    fake_input: FakeInput,
) -> None:
    """Test unloading while a key is held stops its key_hold events."""
    kbd = fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    commands = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_COMMAND_RECEIVED)
    entry = _entry(
        {CONF_DEVICE_PATH: FAKE_DEVICE_PATH, CONF_DEVICE_NAME: FAKE_DEVICE_NAME},
        **{
            CONF_KEY_TYPES: ["key_up"],
            CONF_EMULATE_KEY_HOLD: True,
            CONF_EMULATE_KEY_HOLD_DELAY: 1.0,
        },
    )
    await _set_up(hass, fake_input, entry)
    await fake_input.press(kbd, 30, KEY_VALUE["key_down"])

    assert await hass.config_entries.async_unload(entry.entry_id)
    await _advance(hass, 60)

    assert commands == []


async def test_reload_one_of_two_entries_reconnects_its_device(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reloading an entry, as its options flow does, reconnects its device.

    The node must be released on unload, or the reloaded entry could never
    claim it while another entry keeps the watcher running.
    """
    kbd = fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    fake_input.add(REMOTE_PATH, REMOTE_NAME)
    await _set_up(hass, fake_input, mock_config_entry)
    await _set_up(hass, fake_input, _remote_entry())

    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await fake_input.settle()

    assert kbd.grab.call_count == 2


async def test_grab_failure_is_retried_on_the_next_node_event(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a device that could not be grabbed connects on its next event."""
    kbd = fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    kbd.grab.side_effect = OSError(errno.EBUSY, "Device or resource busy")
    connected = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_CONNECTED)
    await _set_up(hass, fake_input, mock_config_entry)

    kbd.grab.side_effect = None
    await fake_input.touch(FAKE_DEVICE_REAL_PATH)

    assert kbd.grab.call_count == 2
    assert len(connected) == 2


async def test_device_connects_once_its_permissions_are_set(
    hass: HomeAssistant,
    fake_input: FakeInput,
) -> None:
    """Test a node that cannot be opened when created connects on its ATTRIB.

    udev creates the node first and sets its permissions after.
    """
    await _set_up(hass, fake_input, _remote_entry())
    fake_input.add_unopenable(REMOTE_PATH)
    await fake_input.touch(REMOTE_PATH)

    remote = fake_input.add(REMOTE_PATH, REMOTE_NAME)
    await fake_input.touch(REMOTE_PATH)

    remote.grab.assert_called_once()


@pytest.mark.parametrize(
    "order",
    [pytest.param(1, id="path_entry_first"), pytest.param(-1, id="name_first")],
)
async def test_path_entry_wins_over_name_entry(
    hass: HomeAssistant,
    fake_input: FakeInput,
    order: int,
) -> None:
    """Test the entry configured with a node's link gets it over a name entry.

    This holds at startup and after a replug, whatever order the entries were
    set up in.
    """
    hass.set_state(CoreState.not_running)
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    connected = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_CONNECTED)
    path_entry = _entry(
        {CONF_DEVICE_PATH: FAKE_DEVICE_PATH, CONF_DEVICE_NAME: FAKE_DEVICE_NAME}
    )
    name_entry = _entry({CONF_DEVICE_NAME: FAKE_DEVICE_NAME}, unique_id="by-name")
    entries = [path_entry, name_entry][::order]
    for entry in entries:
        await _set_up(hass, fake_input, entry)

    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await fake_input.settle()
    await fake_input.unplug(FAKE_DEVICE_REAL_PATH)
    await fake_input.plug(
        FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH
    )

    # On replug the name entry gets the node from its node events, and hands
    # it to the path entry once the by-id link appears
    assert [e.data[CONF_DEVICE_DESCRIPTOR] for e in connected] == [
        FAKE_DEVICE_PATH,
        FAKE_DEVICE_REAL_PATH,
        FAKE_DEVICE_PATH,
    ]


async def test_link_to_held_node_keeps_holder_when_path_entry_busy(
    hass: HomeAssistant,
    fake_input: FakeInput,
) -> None:
    """Test a link does not take a node for a path entry that has one already.

    Identical keyboards without a serial share their by-id link, and udev
    points it at the one added last. Handing that node over would disconnect
    the name entry and leave the node to nobody.
    """
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    disconnected = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_DISCONNECTED)
    await _set_up(
        hass,
        fake_input,
        _entry(
            {CONF_DEVICE_PATH: FAKE_DEVICE_PATH, CONF_DEVICE_NAME: FAKE_DEVICE_NAME}
        ),
    )
    await _set_up(
        hass,
        fake_input,
        _entry({CONF_DEVICE_NAME: FAKE_DEVICE_NAME}, unique_id="by-name"),
    )
    second = await fake_input.plug(REMOTE_PATH, FAKE_DEVICE_NAME)

    await fake_input.link(FAKE_DEVICE_PATH, REMOTE_PATH)

    second.grab.assert_called_once()
    second.ungrab.assert_not_called()
    assert not disconnected


async def test_same_named_nodes_connect_the_first_node(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a name entry takes the lowest of several same-named nodes.

    The same node wins at startup and for an entry added later, whatever
    order the nodes are listed in.
    """
    fake_input.add("/dev/input/event8", REMOTE_NAME)
    first = fake_input.add(REMOTE_PATH, REMOTE_NAME)
    connected = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_CONNECTED)
    await _set_up(hass, fake_input, mock_config_entry)

    await _set_up(hass, fake_input, _remote_entry())

    first.grab.assert_called_once()
    assert [e.data[CONF_DEVICE_DESCRIPTOR] for e in connected] == [REMOTE_PATH]


async def test_link_added_while_unwatched_connects_on_next_event(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a link added while by-id was unwatched connects on any next event.

    Retrying the watch rechecks the waiting entries, since that link produced
    no event.
    """
    await _set_up(hass, fake_input, mock_config_entry)
    await _set_up(
        hass,
        fake_input,
        _entry({CONF_DEVICE_PATH: FAKE_DEVICE_PATH_2, CONF_DEVICE_NAME: "Remote"}),
    )
    fake_input.watch_errors[DEVINPUT_BY_ID] = OSError(errno.ENOSPC, "No space")
    await fake_input.plug(
        FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH
    )
    remote = await fake_input.plug(
        "/dev/input/event6", "Remote", link=FAKE_DEVICE_PATH_2
    )
    remote.grab.assert_not_called()

    fake_input.watch_errors.clear()
    await fake_input.plug("/dev/input/event9", "Mouse")

    remote.grab.assert_called_once()


async def test_unload_removes_the_stop_listener(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading the last entry removes its Home Assistant stop listener."""
    before = hass.bus.async_listeners().get(EVENT_HOMEASSISTANT_STOP, 0)
    await _set_up(hass, fake_input, mock_config_entry)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await fake_input.settle()

    assert hass.bus.async_listeners().get(EVENT_HOMEASSISTANT_STOP, 0) == before


async def test_listing_error_does_not_stop_monitoring(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test startup survives a node vanishing while the devices are listed.

    evdev checks each node after listing the directory, which raises if the
    node is removed in between.
    """
    fake_input.listing_error = FileNotFoundError(errno.ENOENT, "No such file")
    await _set_up(hass, fake_input, mock_config_entry)
    fake_input.listing_error = None

    kbd = await fake_input.plug(
        FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH
    )

    kbd.grab.assert_called_once()


async def test_event_without_a_node_is_ignored(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an event on /dev/input itself, like a queue overflow, opens nothing."""
    await _set_up(hass, fake_input, mock_config_entry)
    fake_input.opened.clear()
    assert fake_input.inotify is not None

    fake_input.inotify.queue.put_nowait(
        SimpleNamespace(
            name=None, mask=Mask.Q_OVERFLOW, watch=fake_input.inotify.watches[DEVINPUT]
        )
    )
    await fake_input.settle()

    assert fake_input.opened == []


async def test_unload_during_unplug_teardown_releases_the_device(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading while an unplug teardown ungrabs still releases the device.

    Stopping cancels the watcher running that teardown, which must still close
    the device and report the disconnect, and must not keep the unload waiting.
    """
    kbd = fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    disconnected = async_capture_events(hass, EVENT_KEYBOARD_REMOTE_DISCONNECTED)
    await _set_up(hass, fake_input, mock_config_entry)
    ungrabbing, release = kbd.ungrab.hold()

    fake_input.remove_node(FAKE_DEVICE_REAL_PATH)
    await _wait_in_executor(hass, ungrabbing)
    unload = hass.async_create_task(
        hass.config_entries.async_unload(mock_config_entry.entry_id)
    )
    await fake_input.settle(wait_for_executor=False)
    release.set()
    assert await unload
    await fake_input.settle()

    kbd.close.assert_called_once()
    assert len(disconnected) == 1
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
