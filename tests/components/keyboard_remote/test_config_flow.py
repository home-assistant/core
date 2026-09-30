"""Tests for the Keyboard Remote config flow."""

import errno
from typing import Any
from unittest.mock import AsyncMock

import pytest

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
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=data
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


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_all_configured_by_name(
    hass: HomeAssistant, fake_input: FakeInput
) -> None:
    """Test a device configured by name counts as found, not as missing."""
    fake_input.add(BT_REMOTE_PATH, BT_REMOTE_NAME)
    MockConfigEntry(
        domain=DOMAIN, unique_id=BT_REMOTE_NAME, data={CONF_DEVICE_NAME: BT_REMOTE_NAME}
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
    """Test a YAML descriptor is stored with the by-id link it resolves to."""
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
    """Test YAML falls back to its configured identity without a single link."""
    for path, link in devices:
        fake_input.add(path, FAKE_DEVICE_NAME, link=link)
    fake_input.by_id_error = by_id_error

    result = await _import(hass, import_data)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == expected_unique_id
    assert result["data"] == expected_data


@pytest.mark.usefixtures("fake_input")
async def test_import_cannot_identify(hass: HomeAssistant) -> None:
    """Test a YAML block with neither descriptor nor name aborts."""
    result = await _import(hass, {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_identify_device"


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


@pytest.mark.parametrize(
    ("import_data", "legacy_unique_id"),
    [
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
    legacy_unique_id: str,
) -> None:
    """Test a re-import migrates the earlier entry instead of duplicating it.

    The first import can run before udev has created the by-id link, which
    leaves the entry keyed by the raw descriptor or name. Once the link
    exists, the same YAML resolves to the by-id basename.
    """
    existing = MockConfigEntry(
        domain=DOMAIN,
        unique_id=legacy_unique_id,
        data={CONF_DEVICE_PATH: legacy_unique_id, CONF_DEVICE_NAME: FAKE_DEVICE_NAME},
    )
    existing.add_to_hass(hass)
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)

    result = await _import(hass, import_data)

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
    hass: HomeAssistant, fake_input: FakeInput, title: str, expected_title: str
) -> None:
    """Test adoption replaces the raw path stored as name while unplugged.

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
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)

    result = await _import(hass, {"device_descriptor": FAKE_DEVICE_REAL_PATH})

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
        pytest.param({"device_name": FAKE_DEVICE_NAME}, FAKE_DEVICE_NAME, id="name"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_does_not_adopt_onto_a_taken_unique_id(
    hass: HomeAssistant,
    fake_input: FakeInput,
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
    fake_input.add(FAKE_DEVICE_REAL_PATH, FAKE_DEVICE_NAME, link=FAKE_DEVICE_PATH)

    result = await _import(hass, import_data)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
    assert legacy.unique_id == legacy_unique_id
    assert legacy.data[CONF_DEVICE_PATH] == legacy_unique_id


@pytest.mark.parametrize(
    ("delay", "repeat", "expected_delay", "expected_repeat"),
    [
        pytest.param(10, 0, 5.0, 0.001, id="above_and_below"),
        pytest.param(0, 2, 0.01, 1.0, id="below_and_above"),
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

    YAML accepted any number, and a value outside the range would make the
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
    assert f"Imported emulate_key_hold_delay of {delay} is outside" in caplog.text
    assert f"Imported emulate_key_hold_repeat of {repeat} is outside" in caplog.text


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
