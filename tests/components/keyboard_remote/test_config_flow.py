"""Tests for the Keyboard Remote config flow."""

import errno
import math
from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.keyboard_remote import CONFIG_SCHEMA
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
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    BUS_HOST,
    FAKE_BY_ID_BASENAME,
    FAKE_DEVICE_NAME,
    FAKE_DEVICE_NAME_2,
    FAKE_DEVICE_PATH,
    FAKE_DEVICE_PATH_2,
    FAKE_DEVICE_REAL_PATH,
    FakeInput,
)

from tests.common import MockConfigEntry

BT_REMOTE_NAME = "BT Remote"
BY_PATH_LINK = "/dev/input/by-path/pci-0000:00:14.0-usb-0:1:1.0-event-kbd"
BT_REMOTE_PATH = "/dev/input/event7"
REMOTE_REAL_PATH = "/dev/input/event6"
REMOTE_BY_ID_BASENAME = "usb-Test_Remote-event-kbd"

DEFAULT_OPTIONS = {
    CONF_KEY_TYPES: DEFAULT_KEY_TYPES,
    CONF_EMULATE_KEY_HOLD: DEFAULT_EMULATE_KEY_HOLD,
    CONF_EMULATE_KEY_HOLD_DELAY: DEFAULT_EMULATE_KEY_HOLD_DELAY,
    CONF_EMULATE_KEY_HOLD_REPEAT: DEFAULT_EMULATE_KEY_HOLD_REPEAT,
}


def _offered(result: ConfigFlowResult) -> list[dict[str, str]]:
    """Return the devices the user step offers."""
    return result["data_schema"].schema[CONF_DEVICE_PATH].config["options"]


async def _import(hass: HomeAssistant, data: dict[str, Any]) -> ConfigFlowResult:
    """Import a YAML block as validated by the integration's schema."""
    [block] = CONFIG_SCHEMA({DOMAIN: data})[DOMAIN]
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=block
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_creates_entry(
    hass: HomeAssistant, fake_input: FakeInput
) -> None:
    """Test the user step offers a device by its by-id link and adds it."""
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert _offered(result) == [
        {
            "value": FAKE_DEVICE_PATH,
            "label": f"{FAKE_DEVICE_NAME} ({FAKE_BY_ID_BASENAME})",
        }
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE_PATH: FAKE_DEVICE_PATH}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == FAKE_DEVICE_NAME
    assert result["result"].unique_id == FAKE_BY_ID_BASENAME
    assert result["data"] == {
        CONF_DEVICE_PATH: FAKE_DEVICE_PATH,
        CONF_DEVICE_NAME: FAKE_DEVICE_NAME,
    }
    assert result["options"] == DEFAULT_OPTIONS


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_cannot_connect(
    hass: HomeAssistant, fake_input: FakeInput
) -> None:
    """Test a device that cannot be opened when chosen shows an error."""
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    fake_input.add(REMOTE_REAL_PATH, FAKE_DEVICE_NAME_2, link=FAKE_DEVICE_PATH_2)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    fake_input.add_unopenable(FAKE_DEVICE_REAL_PATH)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE_PATH: FAKE_DEVICE_PATH}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    # The form is scanned again, and the device that cannot be opened is gone
    assert [option["value"] for option in _offered(result)] == [FAKE_DEVICE_PATH_2]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE_PATH: FAKE_DEVICE_PATH_2}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_step_no_devices(hass: HomeAssistant, fake_input: FakeInput) -> None:
    """Test the user step aborts when no input device can be offered."""
    fake_input.add("/dev/input/event1", "Headphone Jack", sends_keys=False)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices"


@pytest.mark.parametrize(
    "entry",
    [
        pytest.param(
            MockConfigEntry(
                domain=DOMAIN,
                unique_id=FAKE_BY_ID_BASENAME,
                data={CONF_DEVICE_PATH: FAKE_DEVICE_PATH},
            ),
            id="by_id_link",
        ),
        # Imported from YAML before the by-id link existed, so keyed by the
        # raw node, which the link now listed points at
        pytest.param(
            MockConfigEntry(
                domain=DOMAIN,
                unique_id=FAKE_DEVICE_REAL_PATH,
                data={
                    CONF_DEVICE_PATH: FAKE_DEVICE_REAL_PATH,
                    CONF_DEVICE_DESCRIPTOR: FAKE_DEVICE_REAL_PATH,
                },
            ),
            id="raw_node",
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_all_configured(
    hass: HomeAssistant, fake_input: FakeInput, entry: MockConfigEntry
) -> None:
    """Test the user step aborts when every device is already configured."""
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "all_devices_configured"


@pytest.mark.parametrize(
    "uniq",
    [pytest.param("", id="no_uniq"), pytest.param("aa:bb:cc:dd:ee:01", id="uniq")],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_all_configured_by_name(
    hass: HomeAssistant, fake_input: FakeInput, uniq: str
) -> None:
    """Test a device an entry matches by name counts as found and configured.

    A YAML entry configured by name matches any device of that name, also a
    Bluetooth remote whose own entry would include its uniq.
    """
    fake_input.add(BT_REMOTE_PATH, BT_REMOTE_NAME, uniq=uniq)
    MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_IMPORT,
        unique_id=BT_REMOTE_NAME,
        data={CONF_DEVICE_NAME: BT_REMOTE_NAME},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "all_devices_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_hides_configured_devices(
    hass: HomeAssistant, fake_input: FakeInput, mock_config_entry: MockConfigEntry
) -> None:
    """Test configured devices are not offered and the others can be added."""
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    fake_input.add(REMOTE_REAL_PATH, FAKE_DEVICE_NAME_2, link=FAKE_DEVICE_PATH_2)
    fake_input.add(BT_REMOTE_PATH, BT_REMOTE_NAME)
    mock_config_entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN, unique_id=BT_REMOTE_NAME, data={CONF_DEVICE_NAME: BT_REMOTE_NAME}
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert [option["value"] for option in _offered(result)] == [FAKE_DEVICE_PATH_2]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE_PATH: FAKE_DEVICE_PATH_2}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_PATH] == FAKE_DEVICE_PATH_2


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_offers_device_on_reused_yaml_descriptor(
    hass: HomeAssistant, fake_input: FakeInput
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
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME_2, link=FAKE_DEVICE_PATH_2)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert [option["value"] for option in _offered(result)] == [FAKE_DEVICE_PATH_2]


async def test_user_step_lists_devices(
    hass: HomeAssistant, fake_input: FakeInput
) -> None:
    """Test which devices the user step offers.

    udev creates no by-id link for Bluetooth devices, so those are offered by
    their node, once per name. Nodes that cannot send keys, with or without a
    by-id link, host-bus devices such as the power button, and nodes that
    cannot be opened or are unplugged while inspected are not offered.
    """
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    fake_input.add(BT_REMOTE_PATH, BT_REMOTE_NAME)
    fake_input.add("/dev/input/event8", BT_REMOTE_NAME)
    fake_input.add("/dev/input/event9", "Headphone Jack", sends_keys=False)
    fake_input.add_unopenable("/dev/input/event10")
    fake_input.add("/dev/input/event11", "Power Button", bustype=BUS_HOST)
    fake_input.add(
        "/dev/input/event12",
        "Webcam",
        sends_keys=False,
        link="/dev/input/by-id/usb-Webcam-event-if00",
    )
    unplugged = fake_input.add("/dev/input/event13", "Unplugged")
    unplugged.capabilities.side_effect = OSError(errno.ENODEV, "No such device")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert _offered(result) == [
        {
            "value": FAKE_DEVICE_PATH,
            "label": f"{FAKE_DEVICE_NAME} ({FAKE_BY_ID_BASENAME})",
        },
        {"value": BT_REMOTE_PATH, "label": f"{BT_REMOTE_NAME} (event7)"},
    ]
    unplugged.close.assert_called_once()


@pytest.mark.parametrize(
    "other_link",
    [
        pytest.param(None, id="no_by_id_directory"),
        pytest.param(FAKE_DEVICE_PATH_2, id="by_id_directory"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_creates_name_matched_entry(
    hass: HomeAssistant, fake_input: FakeInput, other_link: str | None
) -> None:
    """Test a device without a by-id link is configured by its name.

    Its node can change when it reconnects, so the entry matches by name, like
    a YAML entry configured by name.
    """
    fake_input.add(BT_REMOTE_PATH, BT_REMOTE_NAME)
    fake_input.add(REMOTE_REAL_PATH, FAKE_DEVICE_NAME_2, link=other_link)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE_PATH: BT_REMOTE_PATH}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == BT_REMOTE_NAME
    assert result["result"].unique_id == BT_REMOTE_NAME
    assert result["data"] == {CONF_DEVICE_NAME: BT_REMOTE_NAME}


REMOTE_1_UNIQ = "aa:bb:cc:dd:ee:01"
REMOTE_2_UNIQ = "aa:bb:cc:dd:ee:02"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_tells_bluetooth_remotes_apart(
    hass: HomeAssistant, fake_input: FakeInput
) -> None:
    """Test identical Bluetooth remotes are told apart by their address.

    evdev reports a Bluetooth device's own address as its uniq. The nodes of
    one composite device share it, and are told apart by their names.
    """
    fake_input.add(BT_REMOTE_PATH, BT_REMOTE_NAME, uniq=REMOTE_1_UNIQ)
    fake_input.add(
        "/dev/input/event8", f"{BT_REMOTE_NAME} Consumer Control", uniq=REMOTE_1_UNIQ
    )
    fake_input.add("/dev/input/event9", BT_REMOTE_NAME, uniq=REMOTE_2_UNIQ)
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{REMOTE_1_UNIQ} {BT_REMOTE_NAME}",
        data={CONF_DEVICE_NAME: BT_REMOTE_NAME, CONF_DEVICE_UNIQ: REMOTE_1_UNIQ},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert _offered(result) == [
        {
            "value": "/dev/input/event8",
            "label": f"{BT_REMOTE_NAME} Consumer Control ({REMOTE_1_UNIQ})",
        },
        {"value": "/dev/input/event9", "label": f"{BT_REMOTE_NAME} ({REMOTE_2_UNIQ})"},
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE_PATH: "/dev/input/event9"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == f"{REMOTE_2_UNIQ} {BT_REMOTE_NAME}"
    assert result["data"] == {
        CONF_DEVICE_NAME: BT_REMOTE_NAME,
        CONF_DEVICE_UNIQ: REMOTE_2_UNIQ,
    }


@pytest.mark.parametrize(
    ("device_path", "unique_id"),
    [
        pytest.param(FAKE_DEVICE_PATH, FAKE_BY_ID_BASENAME, id="by_id_link"),
        pytest.param(BT_REMOTE_PATH, BT_REMOTE_NAME, id="by_name"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_device_configured_meanwhile(
    hass: HomeAssistant, fake_input: FakeInput, device_path: str, unique_id: str
) -> None:
    """Test choosing a device configured while the form was open aborts."""
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    fake_input.add(BT_REMOTE_PATH, BT_REMOTE_NAME)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    MockConfigEntry(domain=DOMAIN, unique_id=unique_id, data={}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE_PATH: device_path}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_with_descriptor_and_by_id(
    hass: HomeAssistant, fake_input: FakeInput
) -> None:
    """Test a YAML node descriptor is stored with the by-id link it resolves to."""
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)

    result = await _import(
        hass,
        {
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
    assert result["data"] == {
        CONF_DEVICE_PATH: FAKE_DEVICE_PATH,
        CONF_DEVICE_NAME: FAKE_DEVICE_NAME,
        CONF_DEVICE_DESCRIPTOR: FAKE_DEVICE_REAL_PATH,
    }
    assert result["options"] == {
        CONF_KEY_TYPES: ["key_up", "key_down"],
        CONF_EMULATE_KEY_HOLD: True,
        CONF_EMULATE_KEY_HOLD_DELAY: 0.5,
        CONF_EMULATE_KEY_HOLD_REPEAT: 0.05,
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_with_name_and_by_id(
    hass: HomeAssistant, fake_input: FakeInput
) -> None:
    """Test a YAML name matching one node is stored with that node's by-id link."""
    fake_input.add_unopenable("/dev/input/event1")
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)

    result = await _import(hass, {"device_name": FAKE_DEVICE_NAME})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == FAKE_BY_ID_BASENAME
    assert result["data"] == {
        CONF_DEVICE_PATH: FAKE_DEVICE_PATH,
        CONF_DEVICE_NAME: FAKE_DEVICE_NAME,
    }


@pytest.mark.parametrize(
    ("devices", "by_id_error", "import_data", "expected_unique_id", "expected_data"),
    [
        pytest.param(
            [(FAKE_DEVICE_REAL_PATH, None)],
            None,
            {"device_descriptor": FAKE_DEVICE_REAL_PATH},
            FAKE_DEVICE_REAL_PATH,
            {
                CONF_DEVICE_PATH: FAKE_DEVICE_REAL_PATH,
                CONF_DEVICE_NAME: FAKE_DEVICE_NAME,
                CONF_DEVICE_DESCRIPTOR: FAKE_DEVICE_REAL_PATH,
            },
            id="descriptor_without_by_id_link",
        ),
        pytest.param(
            [(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_PATH)],
            OSError(errno.EACCES, "Permission denied"),
            {"device_descriptor": FAKE_DEVICE_REAL_PATH},
            FAKE_DEVICE_REAL_PATH,
            {
                CONF_DEVICE_PATH: FAKE_DEVICE_REAL_PATH,
                CONF_DEVICE_NAME: FAKE_DEVICE_NAME,
                CONF_DEVICE_DESCRIPTOR: FAKE_DEVICE_REAL_PATH,
            },
            id="by_id_directory_unreadable",
        ),
        # The device name is unknown while it is unplugged, so the descriptor
        # stands in for it
        pytest.param(
            [],
            None,
            {"device_descriptor": FAKE_DEVICE_REAL_PATH},
            FAKE_DEVICE_REAL_PATH,
            {
                CONF_DEVICE_PATH: FAKE_DEVICE_REAL_PATH,
                CONF_DEVICE_NAME: FAKE_DEVICE_REAL_PATH,
                CONF_DEVICE_DESCRIPTOR: FAKE_DEVICE_REAL_PATH,
            },
            id="descriptor_device_absent",
        ),
        # A by-id descriptor is stable on its own, plugged in or not
        pytest.param(
            [],
            None,
            {"device_descriptor": FAKE_DEVICE_PATH},
            FAKE_BY_ID_BASENAME,
            {
                CONF_DEVICE_PATH: FAKE_DEVICE_PATH,
                CONF_DEVICE_NAME: FAKE_DEVICE_PATH,
                CONF_DEVICE_DESCRIPTOR: FAKE_DEVICE_PATH,
            },
            id="by_id_descriptor_device_absent",
        ),
        pytest.param(
            [],
            None,
            {"device_name": FAKE_DEVICE_NAME},
            FAKE_DEVICE_NAME,
            {CONF_DEVICE_NAME: FAKE_DEVICE_NAME},
            id="name_device_absent",
        ),
        # The node is whatever the kernel assigned this boot, so storing it
        # would let it outrank the configured name
        pytest.param(
            [(FAKE_DEVICE_REAL_PATH, None)],
            None,
            {"device_name": FAKE_DEVICE_NAME},
            FAKE_DEVICE_NAME,
            {CONF_DEVICE_NAME: FAKE_DEVICE_NAME},
            id="name_without_by_id_link",
        ),
        # A composite keyboard reports the same name on each node, and taking
        # the first node's link would pin the entry to an arbitrary node
        pytest.param(
            [(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_PATH), ("/dev/input/event4", None)],
            None,
            {"device_name": FAKE_DEVICE_NAME},
            FAKE_DEVICE_NAME,
            {CONF_DEVICE_NAME: FAKE_DEVICE_NAME},
            id="name_on_several_nodes",
        ),
        # A by-path or custom udev link already tells apart identical devices
        # that share one by-id link
        pytest.param(
            [(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_PATH)],
            None,
            {"device_descriptor": BY_PATH_LINK},
            BY_PATH_LINK,
            {
                CONF_DEVICE_PATH: BY_PATH_LINK,
                CONF_DEVICE_NAME: FAKE_DEVICE_NAME,
                CONF_DEVICE_DESCRIPTOR: BY_PATH_LINK,
            },
            id="by_path_descriptor",
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_fallback_identity(
    hass: HomeAssistant,
    fake_input: FakeInput,
    devices: list[tuple[str, str | None]],
    by_id_error: OSError | None,
    import_data: dict[str, str],
    expected_unique_id: str,
    expected_data: dict[str, str],
) -> None:
    """Test YAML keeps its own identity unless it resolves to one by-id link."""
    for path, link in devices:
        fake_input.add(path, FAKE_DEVICE_NAME, link=link)
    fake_input.links[BY_PATH_LINK] = FAKE_DEVICE_REAL_PATH
    fake_input.by_id_error = by_id_error

    result = await _import(hass, import_data)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == expected_unique_id
    assert result["data"] == expected_data


@pytest.mark.parametrize(
    "import_data",
    [
        pytest.param({"device_descriptor": FAKE_DEVICE_PATH}, id="by_id_descriptor"),
        pytest.param({"device_descriptor": FAKE_DEVICE_REAL_PATH}, id="node"),
        pytest.param({"device_name": FAKE_DEVICE_NAME}, id="name"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_again_while_unplugged_keeps_one_entry(
    hass: HomeAssistant, fake_input: FakeInput, import_data: dict[str, str]
) -> None:
    """Test re-importing the same YAML with the device unplugged adds nothing.

    The import runs on every start. Resolved while the device is unplugged,
    the YAML would otherwise give a different identity than the first time.
    """
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    await _import(hass, import_data)
    [entry] = hass.config_entries.async_entries(DOMAIN)
    unique_id, data = entry.unique_id, dict(entry.data)
    fake_input.devices.clear()
    fake_input.links.clear()

    result = await _import(hass, import_data)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [entry]
    assert (entry.unique_id, dict(entry.data)) == (unique_id, data)


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_already_configured(
    hass: HomeAssistant, fake_input: FakeInput, mock_config_entry: MockConfigEntry
) -> None:
    """Test YAML import aborts when its device is already configured."""
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)
    mock_config_entry.add_to_hass(hass)

    result = await _import(hass, {"device_descriptor": FAKE_DEVICE_REAL_PATH})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


def _legacy_import_entry(import_data: dict[str, str], name: str) -> MockConfigEntry:
    """Create an entry as imported from YAML before the device had a link."""
    if descriptor := import_data.get("device_descriptor"):
        data = {
            CONF_DEVICE_PATH: descriptor,
            CONF_DEVICE_NAME: name,
            CONF_DEVICE_DESCRIPTOR: descriptor,
        }
    else:
        data = {CONF_DEVICE_NAME: name}
    return MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_IMPORT,
        unique_id=descriptor or name,
        title=name,
        data=data,
    )


@pytest.mark.parametrize(
    ("import_data", "first_name"),
    [
        # The device was unplugged at the first import, so its name is unknown
        pytest.param(
            {"device_descriptor": FAKE_DEVICE_REAL_PATH},
            FAKE_DEVICE_REAL_PATH,
            id="descriptor",
        ),
        pytest.param({"device_name": FAKE_DEVICE_NAME}, FAKE_DEVICE_NAME, id="name"),
    ],
)
async def test_import_adopts_entry_created_before_by_id_existed(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_setup_entry: AsyncMock,
    import_data: dict[str, str],
    first_name: str,
) -> None:
    """Test a re-import moves the earlier entry onto the device's by-id link.

    The first import can run before udev created the link, which leaves the
    entry keyed by the raw descriptor or name.
    """
    existing = _legacy_import_entry(import_data, first_name)
    existing.add_to_hass(hass)
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)

    result = await _import(hass, import_data)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [existing]
    assert existing.unique_id == FAKE_BY_ID_BASENAME
    assert existing.data[CONF_DEVICE_PATH] == FAKE_DEVICE_PATH
    assert existing.data[CONF_DEVICE_NAME] == FAKE_DEVICE_NAME
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
async def test_import_adoption_refreshes_fallback_title(
    hass: HomeAssistant, fake_input: FakeInput, title: str, expected_title: str
) -> None:
    """Test adoption replaces the raw path the entry was titled with.

    A title the user has changed since is kept.
    """
    import_data = {"device_descriptor": FAKE_DEVICE_REAL_PATH}
    existing = _legacy_import_entry(import_data, FAKE_DEVICE_REAL_PATH)
    existing.add_to_hass(hass)
    hass.config_entries.async_update_entry(existing, title=title)
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)

    await _import(hass, import_data)

    assert existing.title == expected_title


@pytest.mark.parametrize(
    ("import_data", "first_name"),
    [
        pytest.param(
            {"device_descriptor": FAKE_DEVICE_REAL_PATH},
            FAKE_DEVICE_REAL_PATH,
            id="descriptor",
        ),
        pytest.param({"device_name": FAKE_DEVICE_NAME}, FAKE_DEVICE_NAME, id="name"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_does_not_adopt_onto_a_taken_unique_id(
    hass: HomeAssistant,
    fake_input: FakeInput,
    mock_config_entry: MockConfigEntry,
    import_data: dict[str, str],
    first_name: str,
) -> None:
    """Test the legacy entry is left alone when the by-id ID is already in use.

    The user added the device through the UI before the YAML was re-imported,
    so adopting would give both entries the same unique ID.
    """
    mock_config_entry.add_to_hass(hass)
    legacy = _legacy_import_entry(import_data, first_name)
    legacy.add_to_hass(hass)
    unique_id, data = legacy.unique_id, dict(legacy.data)
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)

    result = await _import(hass, import_data)

    assert result["type"] is FlowResultType.ABORT
    assert (legacy.unique_id, dict(legacy.data)) == (unique_id, data)


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_does_not_adopt_onto_another_device(
    hass: HomeAssistant, fake_input: FakeInput
) -> None:
    """Test a node descriptor now naming a different device leaves the entry.

    The kernel may hand the node to another device after a reboot, and the
    entry knows the name of the device it was created for.
    """
    import_data = {"device_descriptor": FAKE_DEVICE_REAL_PATH}
    legacy = _legacy_import_entry(import_data, "Old Keyboard")
    legacy.add_to_hass(hass)
    fake_input.add(FAKE_DEVICE_REAL_PATH, "USB Mouse", link=FAKE_DEVICE_PATH)

    result = await _import(hass, import_data)

    assert result["type"] is FlowResultType.ABORT
    assert legacy.unique_id == FAKE_DEVICE_REAL_PATH
    assert legacy.data[CONF_DEVICE_NAME] == "Old Keyboard"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_leaves_entries_added_in_the_ui_alone(
    hass: HomeAssistant, fake_input: FakeInput
) -> None:
    """Test a YAML name never rewrites an entry the user added in the UI."""
    ui_entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        unique_id=FAKE_DEVICE_NAME,
        data={CONF_DEVICE_NAME: FAKE_DEVICE_NAME},
    )
    ui_entry.add_to_hass(hass)
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)

    await _import(hass, {"device_name": FAKE_DEVICE_NAME})

    assert ui_entry.unique_id == FAKE_DEVICE_NAME
    assert dict(ui_entry.data) == {CONF_DEVICE_NAME: FAKE_DEVICE_NAME}


@pytest.mark.parametrize(
    ("delay", "repeat", "expected_delay", "expected_repeat"),
    [
        pytest.param(10, 0, 5.0, 0.001, id="above_and_below"),
        pytest.param(-1, 2, 0.01, 1.0, id="negative_and_above"),
        pytest.param(math.nan, math.nan, 0.01, 0.001, id="not_a_number"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_clamps_hold_timing(
    hass: HomeAssistant,
    fake_input: FakeInput,
    caplog: pytest.LogCaptureFixture,
    delay: float,
    repeat: float,
    expected_delay: float,
    expected_repeat: float,
) -> None:
    """Test imported hold timing is fitted into the options form's range.

    YAML takes any number, and a value outside the range would make the
    options form reject its own pre-filled value.
    """
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)

    result = await _import(
        hass,
        {
            "device_descriptor": FAKE_DEVICE_REAL_PATH,
            "emulate_key_hold_delay": delay,
            "emulate_key_hold_repeat": repeat,
        },
    )

    assert result["options"][CONF_EMULATE_KEY_HOLD_DELAY] == expected_delay
    assert result["options"][CONF_EMULATE_KEY_HOLD_REPEAT] == expected_repeat
    assert "Imported emulate_key_hold_delay of" in caplog.text
    assert "Imported emulate_key_hold_repeat of" in caplog.text


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_without_key_types_uses_the_default(
    hass: HomeAssistant, fake_input: FakeInput, caplog: pytest.LogCaptureFixture
) -> None:
    """Test an empty YAML type list imports the default key type.

    An entry with no key types would never fire a command event.
    """
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)

    result = await _import(
        hass, {"device_descriptor": FAKE_DEVICE_REAL_PATH, "type": []}
    )

    assert result["options"][CONF_KEY_TYPES] == DEFAULT_KEY_TYPES
    assert "Imported type lists no key types" in caplog.text


@pytest.mark.usefixtures("fake_input")
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


@pytest.mark.usefixtures("fake_input")
async def test_options_flow_requires_a_key_type(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the options flow rejects an empty key type list.

    An entry with no key types would never fire a command event.
    """
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    options = {
        CONF_KEY_TYPES: [],
        CONF_EMULATE_KEY_HOLD: False,
        CONF_EMULATE_KEY_HOLD_DELAY: 0.5,
        CONF_EMULATE_KEY_HOLD_REPEAT: 0.05,
    }

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=options
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_KEY_TYPES: "no_key_types"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={**options, CONF_KEY_TYPES: ["key_down"]}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_KEY_TYPES] == ["key_down"]


@pytest.mark.parametrize(
    ("data", "expected_device"),
    [
        pytest.param(
            {CONF_DEVICE_PATH: FAKE_DEVICE_PATH, CONF_DEVICE_NAME: FAKE_DEVICE_NAME},
            FAKE_DEVICE_PATH,
            id="by_path",
        ),
        pytest.param({CONF_DEVICE_NAME: BT_REMOTE_NAME}, BT_REMOTE_NAME, id="by_name"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_flow_shows_device(
    hass: HomeAssistant,
    data: dict[str, str],
    expected_device: str,
) -> None:
    """Test the options flow names the device, by name if it has no path."""
    entry = MockConfigEntry(domain=DOMAIN, data=data, options={})
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"] == {"device": expected_device}
