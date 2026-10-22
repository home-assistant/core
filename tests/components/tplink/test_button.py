"""Tests for tplink button platform."""

from unittest.mock import PropertyMock

from freezegun.api import FrozenDateTimeFactory
from kasa import (
    AuthenticationError,
    Device,
    DeviceError,
    Feature,
    KasaException,
    Module,
    TimeoutError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.tplink.button import BUTTON_DESCRIPTIONS
from homeassistant.components.tplink.const import DOMAIN
from homeassistant.components.tplink.entity import EXCLUDED_FEATURES
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    CONF_HOST,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from . import (
    _mocked_device,
    _mocked_feature,
    _mocked_strip_children,
    _patch_connect,
    _patch_discovery,
    setup_automation,
    setup_platform_for_device,
    snapshot_platform,
)
from .const import DEVICE_ID, MAC_ADDRESS

PTZ_PRESET_ENTITY_ID = "button.my_device_go_to_preset_door"
FRONT_CAMERA_DOOR_ENTITY_ID = "button.front_camera_go_to_preset_door"
BACK_CAMERA_DOOR_ENTITY_ID = "button.back_camera_go_to_preset_door"


@pytest.fixture
def create_deprecated_button_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
):
    """Create the entity so it is not ignored by the deprecation check."""
    mock_config_entry.add_to_hass(hass)

    def create_entry(device_name, device_id, key):
        unique_id = f"{device_id}_{key}"

        entity_registry.async_get_or_create(
            domain=BUTTON_DOMAIN,
            platform=DOMAIN,
            unique_id=unique_id,
            suggested_object_id=f"{device_name}_{key}",
            config_entry=mock_config_entry,
        )

    create_entry("my_device", "123456789ABCDEFGH", "stop_alarm")
    create_entry("my_device", "123456789ABCDEFGH", "test_alarm")


@pytest.fixture
def create_deprecated_child_button_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
):
    """Create the entity so it is not ignored by the deprecation check."""

    def create_entry(device_name, key):
        for plug_id in range(2):
            unique_id = f"PLUG{plug_id}DEVICEID_{key}"
            entity_registry.async_get_or_create(
                domain=BUTTON_DOMAIN,
                platform=DOMAIN,
                unique_id=unique_id,
                suggested_object_id=f"my_device_plug{plug_id}_{key}",
                config_entry=mock_config_entry,
            )

    create_entry("my_device", "stop_alarm")
    create_entry("my_device", "test_alarm")


@pytest.fixture
def mocked_hub_with_cameras() -> Device:
    """Return mocked hub with two PTZ cameras that use the same preset ids."""
    cameras = [
        _mocked_device(
            alias=alias,
            device_id=device_id,
            modules=[Module.PanTilt],
            device_type=Device.Type.Camera,
        )
        for alias, device_id in (
            ("Front camera", "FRONTCAMERAID"),
            ("Back camera", "BACKCAMERAID"),
        )
    ]
    return _mocked_device(alias="hub", children=cameras, device_type=Device.Type.Hub)


@pytest.fixture
def mocked_feature_button() -> Feature:
    """Return mocked tplink button feature."""
    return _mocked_feature(
        "test_alarm",
        value="<Action>",
        name="Test alarm",
        type_=Feature.Type.Action,
        category=Feature.Category.Primary,
    )


async def test_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    create_deprecated_button_entities,
) -> None:
    """Test button states."""
    features = {description.key for description in BUTTON_DESCRIPTIONS}
    features.update(EXCLUDED_FEATURES)
    device = _mocked_device(
        alias="my_device", features=features, modules=[Module.PanTilt]
    )

    await setup_platform_for_device(hass, mock_config_entry, Platform.BUTTON, device)
    await snapshot_platform(
        hass, entity_registry, device_registry, snapshot, mock_config_entry.entry_id
    )

    for excluded in EXCLUDED_FEATURES:
        assert hass.states.get(f"sensor.my_device_{excluded}") is None


async def test_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mocked_feature_button: Feature,
    create_deprecated_button_entities,
) -> None:
    """Test button unique ids."""
    mocked_feature = mocked_feature_button
    plug = _mocked_device(alias="my_device", features=[mocked_feature])
    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # The entity_id is based on standard name from core.
    entity_id = "button.my_device_test_alarm"
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == f"{DEVICE_ID}_{mocked_feature.id}"


async def test_button_children(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mocked_feature_button: Feature,
    create_deprecated_button_entities,
    create_deprecated_child_button_entities,
) -> None:
    """Test button children."""
    mocked_feature = mocked_feature_button
    plug = _mocked_device(
        alias="my_device",
        features=[mocked_feature],
        children=_mocked_strip_children(features=[mocked_feature]),
    )
    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "button.my_device_test_alarm"
    entity = entity_registry.async_get(entity_id)
    assert entity
    device = device_registry.async_get(entity.device_id)

    for plug_id in range(2):
        child_entity_id = f"button.my_device_plug{plug_id}_test_alarm"
        child_entity = entity_registry.async_get(child_entity_id)
        assert child_entity
        assert child_entity.unique_id == f"PLUG{plug_id}DEVICEID_{mocked_feature.id}"
        assert child_entity.device_id != entity.device_id
        child_device = device_registry.async_get(child_entity.device_id)
        assert child_device
        assert child_device.via_device_id == device.id


async def test_button_press(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mocked_feature_button: Feature,
    create_deprecated_button_entities,
) -> None:
    """Test a number entity limits and setting values."""
    mocked_feature = mocked_feature_button
    plug = _mocked_device(alias="my_device", features=[mocked_feature])
    with _patch_discovery(device=plug), _patch_connect(device=plug):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "button.my_device_test_alarm"
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == f"{DEVICE_ID}_test_alarm"

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mocked_feature.set_value.assert_called_with(True)


async def test_button_not_exists_with_deprecation(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mocked_feature_button: Feature,
) -> None:
    """Test deprecated buttons are not created if they don't previously exist."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    config_entry.add_to_hass(hass)
    entity_id = "button.my_device_test_alarm"

    assert not hass.states.get(entity_id)
    mocked_feature = mocked_feature_button
    dev = _mocked_device(alias="my_device", features=[mocked_feature])
    with _patch_discovery(device=dev), _patch_connect(device=dev):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert not entity_registry.async_get(entity_id)
    assert not er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    assert not hass.states.get(entity_id)


@pytest.mark.parametrize(
    ("entity_disabled", "entity_has_automations"),
    [
        pytest.param(False, False, id="without-automations"),
        pytest.param(False, True, id="with-automations"),
        pytest.param(True, False, id="disabled"),
    ],
)
async def test_button_exists_with_deprecation(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mocked_feature_button: Feature,
    entity_disabled: bool,
    entity_has_automations: bool,
) -> None:
    """Test the deprecated buttons are deleted or raise issues."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "127.0.0.1"}, unique_id=MAC_ADDRESS
    )
    config_entry.add_to_hass(hass)

    object_id = "my_device_test_alarm"
    entity_id = f"button.{object_id}"
    unique_id = f"{DEVICE_ID}_test_alarm"
    issue_id = f"deprecated_entity_{entity_id}_automation.test_automation"

    if entity_has_automations:
        await setup_automation(hass, "test_automation", entity_id)

    entity = entity_registry.async_get_or_create(
        domain=BUTTON_DOMAIN,
        platform=DOMAIN,
        unique_id=unique_id,
        suggested_object_id=object_id,
        config_entry=config_entry,
        disabled_by=er.RegistryEntryDisabler.USER if entity_disabled else None,
    )
    assert entity.entity_id == entity_id
    assert not hass.states.get(entity_id)

    mocked_feature = mocked_feature_button
    dev = _mocked_device(alias="my_device", features=[mocked_feature])
    with _patch_discovery(device=dev), _patch_connect(device=dev):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entity = entity_registry.async_get(entity_id)
    # entity and state will be none if removed from registry
    assert (entity is None) == entity_disabled
    assert (hass.states.get(entity_id) is None) == entity_disabled

    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert (
        issue is not None and issue.config_entry_id == config_entry.entry_id
    ) == entity_has_automations


async def test_ptz_preset_button_press(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test pressing a PTZ preset button moves the camera to that preset."""
    camera = _mocked_device(alias="my_device", modules=[Module.PanTilt])
    await setup_platform_for_device(hass, mock_config_entry, Platform.BUTTON, camera)

    entity = entity_registry.async_get(PTZ_PRESET_ENTITY_ID)
    assert entity
    assert entity.unique_id == f"{DEVICE_ID}_ptz_preset_1"

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: PTZ_PRESET_ENTITY_ID},
        blocking=True,
    )
    camera.modules[Module.PanTilt].goto_preset.assert_called_once_with("1")


@pytest.mark.parametrize(
    ("exception_type", "msg", "reauth_expected"),
    [
        pytest.param(
            AuthenticationError,
            "Device authentication error async_press: test error",
            True,
            id="authentication",
        ),
        pytest.param(
            TimeoutError,
            "Timeout communicating with the device async_press: test error",
            False,
            id="timeout",
        ),
        pytest.param(
            KasaException,
            "Unable to communicate with the device async_press: test error",
            False,
            id="other",
        ),
    ],
)
async def test_ptz_preset_button_press_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    exception_type: type[Exception],
    msg: str,
    reauth_expected: bool,
) -> None:
    """Test errors from the camera are raised as HomeAssistantError."""
    camera = _mocked_device(alias="my_device", modules=[Module.PanTilt])
    camera.modules[Module.PanTilt].goto_preset.side_effect = exception_type(
        "test error"
    )
    await setup_platform_for_device(hass, mock_config_entry, Platform.BUTTON, camera)

    with pytest.raises(HomeAssistantError, match=msg):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: PTZ_PRESET_ENTITY_ID},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert (
        any(
            flow["handler"] == DOMAIN
            for flow in mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH})
        )
        == reauth_expected
    )


@pytest.mark.parametrize(
    ("is_on", "presets", "entity_id", "expected_state", "expected_name"),
    [
        pytest.param(
            True,
            {"Door": "1", "Garden": "2", "Window": "3"},
            "button.my_device_go_to_preset_window",
            STATE_UNKNOWN,
            "my_device Go to preset Window",
            id="added",
        ),
        pytest.param(
            True,
            {"Front door": "1", "Garden": "2"},
            PTZ_PRESET_ENTITY_ID,
            STATE_UNKNOWN,
            "my_device Go to preset Front door",
            id="renamed",
        ),
        pytest.param(
            True,
            {"Garden": "2"},
            PTZ_PRESET_ENTITY_ID,
            STATE_UNAVAILABLE,
            "my_device Go to preset Door",
            id="removed",
        ),
        pytest.param(
            False,
            {"Door": "1", "Garden": "2"},
            PTZ_PRESET_ENTITY_ID,
            STATE_UNAVAILABLE,
            "my_device Go to preset Door",
            id="camera_off",
        ),
    ],
)
async def test_ptz_preset_buttons_follow_camera(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    is_on: bool,
    presets: dict[str, str],
    entity_id: str,
    expected_state: str,
    expected_name: str,
) -> None:
    """Test PTZ preset buttons follow changes made on the camera after setup."""
    camera = _mocked_device(alias="my_device", modules=[Module.PanTilt])
    await setup_platform_for_device(hass, mock_config_entry, Platform.BUTTON, camera)

    camera.is_on = is_on
    camera.modules[Module.PanTilt].presets = presets
    freezer.tick(30)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == expected_state
    assert state.attributes[ATTR_FRIENDLY_NAME] == expected_name


async def test_ptz_preset_buttons_on_hub_cameras(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mocked_hub_with_cameras: Device,
) -> None:
    """Test hub cameras get their own preset buttons, also for presets added later."""
    hub = mocked_hub_with_cameras
    front_camera, back_camera = hub.children
    await setup_platform_for_device(hass, mock_config_entry, Platform.BUTTON, hub)

    front_entity = entity_registry.async_get(FRONT_CAMERA_DOOR_ENTITY_ID)
    assert front_entity
    assert front_entity.unique_id == "FRONTCAMERAID_ptz_preset_1"
    back_entity = entity_registry.async_get(BACK_CAMERA_DOOR_ENTITY_ID)
    assert back_entity
    assert back_entity.unique_id == "BACKCAMERAID_ptz_preset_1"
    back_device = device_registry.async_get(back_entity.device_id)
    assert back_device
    assert back_device.name == "Back camera"

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: BACK_CAMERA_DOOR_ENTITY_ID},
        blocking=True,
    )
    back_camera.modules[Module.PanTilt].goto_preset.assert_called_once_with("1")
    front_camera.modules[Module.PanTilt].goto_preset.assert_not_called()

    back_camera.modules[Module.PanTilt].presets = {"Door": "1", "Window": "3"}
    freezer.tick(30)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("button.back_camera_go_to_preset_window")
    assert not hass.states.get("button.front_camera_go_to_preset_window")


async def test_ptz_preset_buttons_hub_camera_paired_again(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mocked_hub_with_cameras: Device,
) -> None:
    """Test preset buttons come back when a camera is paired to the hub again."""
    hub = mocked_hub_with_cameras
    cameras = hub.children
    await setup_platform_for_device(hass, mock_config_entry, Platform.BUTTON, hub)
    assert hass.states.get(FRONT_CAMERA_DOOR_ENTITY_ID)

    hub.children = []
    freezer.tick(30)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not hass.states.get(FRONT_CAMERA_DOOR_ENTITY_ID)

    hub.children = cameras
    freezer.tick(30)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(FRONT_CAMERA_DOOR_ENTITY_ID)


async def test_ptz_preset_buttons_hub_camera_read_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mocked_hub_with_cameras: Device,
) -> None:
    """Test a preset read error on one hub camera does not drop the other buttons."""
    hub = mocked_hub_with_cameras
    back_pan_tilt = hub.children[1].modules[Module.PanTilt]
    presets = PropertyMock(side_effect=DeviceError("test error"))
    type(back_pan_tilt).presets = presets
    await setup_platform_for_device(hass, mock_config_entry, Platform.BUTTON, hub)

    assert hass.states.get(FRONT_CAMERA_DOOR_ENTITY_ID)
    assert not hass.states.get(BACK_CAMERA_DOOR_ENTITY_ID)

    presets.side_effect = None
    presets.return_value = {"Door": "1"}
    freezer.tick(30)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(BACK_CAMERA_DOOR_ENTITY_ID)
