"""Test the UniFi Protect global services."""

from collections.abc import Callable, Coroutine
from typing import Any
from unittest.mock import AsyncMock, Mock

import probatio
from pydantic import ValidationError
import pytest
from pytest_homeassistant.common import MockConfigEntry, MockUser
from uiprotect.data import Camera, Chime, Light, PTZPreset
from uiprotect.data.devices import CameraZone
from uiprotect.exceptions import BadRequest, ClientError

from homeassistant.components.unifiprotect.const import (
    ATTR_MESSAGE,
    DOMAIN,
    KEYRINGS_KEY_TYPE,
    KEYRINGS_KEY_TYPE_ID_FINGERPRINT,
    KEYRINGS_KEY_TYPE_ID_NFC,
    KEYRINGS_ULP_ID,
    KEYRINGS_USER_FULL_NAME,
    KEYRINGS_USER_STATUS,
)
from homeassistant.components.unifiprotect.services import (
    ATTR_PRESET,
    ATTR_TRIGGER_ID,
    SERVICE_ADD_DOORBELL_TEXT,
    SERVICE_GET_USER_KEYRING_INFO,
    SERVICE_PTZ_GOTO_PRESET,
    SERVICE_REMOVE_DOORBELL_TEXT,
    SERVICE_REMOVE_PRIVACY_ZONE,
    SERVICE_SET_CHIME_PAIRED,
    SERVICE_TRIGGER_ALARM_WEBHOOK,
)
from homeassistant.config_entries import ConfigEntryDisabler
from homeassistant.const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_NAME,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, Context, HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import patch_ufp_method
from .conftest import UNIFI_MAC
from .utils import MockUFPFixture, init_entry, setup_public_chime


@pytest.fixture(name="device")
async def device_fixture(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, ufp: MockUFPFixture
):
    """Fixture with entry setup to call services with."""

    await init_entry(hass, ufp, [])

    return list(device_registry.devices)[0]


@pytest.fixture(name="subdevice")
async def subdevice_fixture(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    ufp: MockUFPFixture,
    light: Light,
):
    """Fixture with entry setup to call services with."""

    await init_entry(hass, ufp, [light])

    return [d for d in device_registry.devices if d.name != "UnifiProtect"][0]


async def test_global_service_bad_device(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> None:
    """Test global service, invalid device ID."""

    await init_entry(hass, ufp, [])
    nvr = ufp.api.bootstrap.nvr

    with patch_ufp_method(
        nvr, "add_custom_doorbell_message", new_callable=AsyncMock
    ) as mock_method:
        with pytest.raises(ServiceValidationError) as error:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_ADD_DOORBELL_TEXT,
                {ATTR_DEVICE_ID: "bad_device_id", ATTR_MESSAGE: "Test Message"},
                blocking=True,
            )
        assert not mock_method.called

    assert error.value.translation_domain == HOMEASSISTANT_DOMAIN
    assert error.value.translation_key == "service_device_not_found"


async def test_global_service_device_from_other_integration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    ufp: MockUFPFixture,
) -> None:
    """Test a device not owned by a UniFi Protect config entry is rejected."""

    await init_entry(hass, ufp, [])
    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    other_device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={("other", "other-device")},
        name="Other device",
    )

    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_DOORBELL_TEXT,
            {ATTR_DEVICE_ID: other_device.id, ATTR_MESSAGE: "Test Message"},
            blocking=True,
        )

    assert error.value.translation_domain == HOMEASSISTANT_DOMAIN
    assert error.value.translation_key == "service_device_wrong_domain"


async def test_global_service_exception(
    hass: HomeAssistant, device: dr.DeviceEntry, ufp: MockUFPFixture
) -> None:
    """Test global service, unexpected error."""

    nvr = ufp.api.bootstrap.nvr

    with patch_ufp_method(
        nvr,
        "add_custom_doorbell_message",
        new_callable=AsyncMock,
        side_effect=BadRequest,
    ) as mock_method:
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_ADD_DOORBELL_TEXT,
                {ATTR_DEVICE_ID: device.id, ATTR_MESSAGE: "Test Message"},
                blocking=True,
            )
        assert mock_method.called


async def test_add_doorbell_text(
    hass: HomeAssistant, device: dr.DeviceEntry, ufp: MockUFPFixture
) -> None:
    """Test add_doorbell_text service."""

    nvr = ufp.api.bootstrap.nvr

    with patch_ufp_method(
        nvr, "add_custom_doorbell_message", new_callable=AsyncMock
    ) as mock_method:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_DOORBELL_TEXT,
            {ATTR_DEVICE_ID: device.id, ATTR_MESSAGE: "Test Message"},
            blocking=True,
        )
        mock_method.assert_called_once_with("Test Message")


async def test_remove_doorbell_text(
    hass: HomeAssistant, subdevice: dr.DeviceEntry, ufp: MockUFPFixture
) -> None:
    """Test remove_doorbell_text service."""

    nvr = ufp.api.bootstrap.nvr

    with patch_ufp_method(
        nvr, "remove_custom_doorbell_message", new_callable=AsyncMock
    ) as mock_method:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REMOVE_DOORBELL_TEXT,
            {ATTR_DEVICE_ID: subdevice.id, ATTR_MESSAGE: "Test Message"},
            blocking=True,
        )
        mock_method.assert_called_once_with("Test Message")


async def test_add_doorbell_text_disabled_config_entry(
    hass: HomeAssistant, device: dr.DeviceEntry, ufp: MockUFPFixture
) -> None:
    """Test add_doorbell_text service."""
    nvr = ufp.api.bootstrap.nvr

    await hass.config_entries.async_set_disabled_by(
        ufp.entry.entry_id, ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()

    with patch_ufp_method(
        nvr, "add_custom_doorbell_message", new_callable=AsyncMock
    ) as mock_method:
        with pytest.raises(ServiceValidationError) as error:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_ADD_DOORBELL_TEXT,
                {ATTR_DEVICE_ID: device.id, ATTR_MESSAGE: "Test Message"},
                blocking=True,
            )
        assert not mock_method.called

    assert error.value.translation_domain == HOMEASSISTANT_DOMAIN
    assert error.value.translation_key == "service_config_entry_not_loaded"


async def _setup_chime_pairing(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    chime: Chime,
    doorbell: Camera,
) -> tuple[dict[str, Any], Camera, Camera]:
    """Set up a chime and two doorbells, returning the action data and doorbells."""
    camera1 = doorbell.model_copy()
    camera1.name = "Test Camera 1"

    camera2 = doorbell.model_copy()
    camera2.name = "Test Camera 2"

    await init_entry(hass, ufp, [camera1, camera2, chime])

    chime_entry = entity_registry.async_get("button.test_chime_play_chime")
    camera_entry = entity_registry.async_get("event.test_camera_2_doorbell")
    assert chime_entry is not None
    assert camera_entry is not None

    data = {
        ATTR_DEVICE_ID: chime_entry.device_id,
        "doorbells": {
            ATTR_ENTITY_ID: ["event.test_camera_1_doorbell"],
            ATTR_DEVICE_ID: [camera_entry.device_id],
        },
    }
    return data, camera1, camera2


async def test_set_chime_paired_doorbells(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    chime: Chime,
    doorbell: Camera,
) -> None:
    """The paired doorbells are written through the public chime."""
    ufp.api.update_device = AsyncMock()
    setup_public_chime(ufp)
    data, camera1, camera2 = await _setup_chime_pairing(
        hass, entity_registry, ufp, chime, doorbell
    )

    await hass.services.async_call(
        DOMAIN, SERVICE_SET_CHIME_PAIRED, data, blocking=True
    )

    public = ufp.api.public_bootstrap.chimes[chime.id]
    public.set_camera_ids.assert_awaited_once_with(sorted([camera1.id, camera2.id]))
    ufp.api.update_device.assert_not_called()


@pytest.mark.usefixtures("mock_private_only_entities_registered")
@pytest.mark.parametrize(
    "entity_id",
    [
        pytest.param("event.test_camera_1_doorbell", id="event"),
        pytest.param("binary_sensor.test_camera_1_doorbell", id="binary_sensor"),
    ],
)
async def test_set_chime_paired_doorbells_entity_target(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    chime: Chime,
    doorbell: Camera,
    entity_id: str,
) -> None:
    """The doorbell event entity and the deprecated binary sensor both pick a doorbell."""
    setup_public_chime(ufp)
    data, camera1, _ = await _setup_chime_pairing(
        hass, entity_registry, ufp, chime, doorbell
    )
    data["doorbells"] = {ATTR_ENTITY_ID: [entity_id]}

    await hass.services.async_call(
        DOMAIN, SERVICE_SET_CHIME_PAIRED, data, blocking=True
    )

    public = ufp.api.public_bootstrap.chimes[chime.id]
    public.set_camera_ids.assert_awaited_once_with([camera1.id])


@pytest.mark.parametrize(
    "entity_id",
    [
        pytest.param("event.test_camera_1_motion_detection", id="other_event"),
        pytest.param("binary_sensor.test_camera_1_motion", id="other_binary_sensor"),
    ],
)
async def test_set_chime_paired_doorbells_ignores_other_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    chime: Chime,
    doorbell: Camera,
    entity_id: str,
) -> None:
    """Other entities of a doorbell do not pick it."""
    setup_public_chime(ufp)
    data, _, _ = await _setup_chime_pairing(hass, entity_registry, ufp, chime, doorbell)
    assert entity_registry.async_get(entity_id) is not None
    data["doorbells"] = {ATTR_ENTITY_ID: [entity_id]}

    await hass.services.async_call(
        DOMAIN, SERVICE_SET_CHIME_PAIRED, data, blocking=True
    )

    public = ufp.api.public_bootstrap.chimes[chime.id]
    public.set_camera_ids.assert_awaited_once_with([])


async def test_set_chime_paired_doorbells_with_foreign_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    chime: Chime,
    doorbell: Camera,
) -> None:
    """An entity of another integration on the chime device does not matter."""
    setup_public_chime(ufp)
    data, camera1, camera2 = await _setup_chime_pairing(
        hass, entity_registry, ufp, chime, doorbell
    )
    # Leave only an entity of another integration on the chime device, as a
    # helper linked to it would add.
    for entry in er.async_entries_for_device(entity_registry, data[ATTR_DEVICE_ID]):
        entity_registry.async_remove(entry.entity_id)
    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        "sensor",
        "other",
        "not-a-mac",
        config_entry=other_entry,
        device_id=data[ATTR_DEVICE_ID],
    )

    await hass.services.async_call(
        DOMAIN, SERVICE_SET_CHIME_PAIRED, data, blocking=True
    )

    public = ufp.api.public_bootstrap.chimes[chime.id]
    public.set_camera_ids.assert_awaited_once_with(sorted([camera1.id, camera2.id]))


async def test_set_chime_paired_doorbells_readopted_chime(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    chime: Chime,
    doorbell: Camera,
) -> None:
    """The public chime is matched by mac, so a new id after a re-adopt works."""
    setup_public_chime(ufp)
    data, camera1, camera2 = await _setup_chime_pairing(
        hass, entity_registry, ufp, chime, doorbell
    )
    chimes = ufp.api.public_bootstrap.chimes
    public = chimes.pop(chime.id)
    public.id = "new-chime-id"
    chimes[public.id] = public

    await hass.services.async_call(
        DOMAIN, SERVICE_SET_CHIME_PAIRED, data, blocking=True
    )

    public.set_camera_ids.assert_awaited_once_with(sorted([camera1.id, camera2.id]))


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ClientError("boom"), id="client_error"),
        pytest.param(
            ValidationError.from_exception_data("PublicChime", []),
            id="validation_error",
        ),
    ],
)
async def test_set_chime_paired_doorbells_error(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    chime: Chime,
    doorbell: Camera,
    error: Exception,
) -> None:
    """A failed pairing request raises a service error."""
    setup_public_chime(ufp)
    data, _, _ = await _setup_chime_pairing(hass, entity_registry, ufp, chime, doorbell)
    public = ufp.api.public_bootstrap.chimes[chime.id]
    public.set_camera_ids.side_effect = error

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN, SERVICE_SET_CHIME_PAIRED, data, blocking=True
        )

    assert exc_info.value.translation_key == "service_error"


async def test_set_chime_paired_doorbells_without_public_chime(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    ufp: MockUFPFixture,
    chime: Chime,
    doorbell: Camera,
) -> None:
    """Pairing a chime without its public mirror names the chime."""
    data, _, _ = await _setup_chime_pairing(hass, entity_registry, ufp, chime, doorbell)
    assert not ufp.api.public_bootstrap.chimes
    device_registry.async_update_device(data[ATTR_DEVICE_ID], name_by_user="Hallway")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN, SERVICE_SET_CHIME_PAIRED, data, blocking=True
        )

    assert exc_info.value.translation_key == "device_not_available"
    assert exc_info.value.translation_placeholders == {"device_name": "Hallway"}


async def test_set_chime_paired_doorbells_without_public_camera(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    chime: Chime,
    doorbell: Camera,
) -> None:
    """A doorbell without its public mirror is named instead of unpaired."""
    setup_public_chime(ufp)
    data, camera1, _ = await _setup_chime_pairing(
        hass, entity_registry, ufp, chime, doorbell
    )
    del ufp.api.public_bootstrap.cameras[camera1.id]

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN, SERVICE_SET_CHIME_PAIRED, data, blocking=True
        )

    assert exc_info.value.translation_key == "device_not_available"
    assert exc_info.value.translation_placeholders == {"device_name": "Test Camera 1"}
    ufp.api.public_bootstrap.chimes[chime.id].set_camera_ids.assert_not_called()


async def test_set_chime_paired_doorbells_public_nvr_without_mac(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    chime: Chime,
    doorbell: Camera,
) -> None:
    """A public NVR without a mac does not break the not-a-chime check."""
    setup_public_chime(ufp)
    data, _, _ = await _setup_chime_pairing(hass, entity_registry, ufp, chime, doorbell)
    camera_entry = entity_registry.async_get("event.test_camera_2_doorbell")
    assert camera_entry is not None
    data[ATTR_DEVICE_ID] = camera_entry.device_id
    ufp.api.public_bootstrap.nvr.mac = None

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN, SERVICE_SET_CHIME_PAIRED, data, blocking=True
        )

    assert exc_info.value.translation_key == "not_a_chime"


async def test_set_chime_paired_doorbells_device_without_mac(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    ufp: MockUFPFixture,
    chime: Chime,
    doorbell: Camera,
) -> None:
    """A device without a mac cannot be a chime and is named in the error."""
    setup_public_chime(ufp)
    data, _, _ = await _setup_chime_pairing(hass, entity_registry, ufp, chime, doorbell)
    device = device_registry.async_get_or_create(
        config_entry_id=ufp.entry.entry_id,
        identifiers={(DOMAIN, "no-mac")},
        name="No Mac",
    )
    data[ATTR_DEVICE_ID] = device.id

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN, SERVICE_SET_CHIME_PAIRED, data, blocking=True
        )

    assert exc_info.value.translation_key == "device_not_available"
    assert exc_info.value.translation_placeholders == {"device_name": "No Mac"}
    ufp.api.public_bootstrap.chimes[chime.id].set_camera_ids.assert_not_called()


async def test_set_chime_paired_doorbells_unpair_all(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    chime: Chime,
    doorbell: Camera,
) -> None:
    """Without doorbells the chime is unpaired from all of them."""
    setup_public_chime(ufp)
    data, _, _ = await _setup_chime_pairing(hass, entity_registry, ufp, chime, doorbell)
    del data["doorbells"]

    await hass.services.async_call(
        DOMAIN, SERVICE_SET_CHIME_PAIRED, data, blocking=True
    )

    public = ufp.api.public_bootstrap.chimes[chime.id]
    public.set_camera_ids.assert_awaited_once_with([])


@pytest.mark.parametrize(
    ("picked", "device_name"),
    [
        pytest.param("camera", "Test Camera 2", id="camera"),
        pytest.param("nvr", "UnifiProtect", id="nvr"),
    ],
)
async def test_set_chime_paired_doorbells_not_a_chime(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    ufp: MockUFPFixture,
    chime: Chime,
    doorbell: Camera,
    picked: str,
    device_name: str,
) -> None:
    """A device that is not a chime is rejected by name."""
    setup_public_chime(ufp)
    data, _, camera2 = await _setup_chime_pairing(
        hass, entity_registry, ufp, chime, doorbell
    )
    mac = {"camera": camera2.mac, "nvr": ufp.api.bootstrap.nvr.mac}[picked]
    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, dr.format_mac(mac)), ufp.entry.entry_id
    )
    assert device is not None
    data[ATTR_DEVICE_ID] = device.id

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN, SERVICE_SET_CHIME_PAIRED, data, blocking=True
        )

    assert exc_info.value.translation_key == "not_a_chime"
    assert exc_info.value.translation_placeholders == {"device_name": device_name}
    ufp.api.public_bootstrap.chimes[chime.id].set_camera_ids.assert_not_called()


async def test_remove_privacy_zone_no_zone(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """Test remove_privacy_zone service."""

    ufp.api.update_device = AsyncMock()
    doorbell.privacy_zones = []

    await init_entry(hass, ufp, [doorbell])

    camera_entry = entity_registry.async_get("event.test_camera_doorbell")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REMOVE_PRIVACY_ZONE,
            {ATTR_DEVICE_ID: camera_entry.device_id, ATTR_NAME: "Testing"},
            blocking=True,
        )
    ufp.api.update_device.assert_not_called()


async def test_remove_privacy_zone(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """Test remove_privacy_zone service."""

    ufp.api.update_device = AsyncMock()
    doorbell.privacy_zones = [
        CameraZone(id=0, name="Testing", color="#FF0000", points=[(0, 0), (1, 1)])
    ]

    await init_entry(hass, ufp, [doorbell])

    camera_entry = entity_registry.async_get("event.test_camera_doorbell")

    await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_PRIVACY_ZONE,
        {ATTR_DEVICE_ID: camera_entry.device_id, ATTR_NAME: "Testing"},
        blocking=True,
    )
    ufp.api.update_device.assert_called()
    assert not doorbell.privacy_zones


async def get_user_keyring_info(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """Test get_user_keyring_info service."""

    ulp_user = Mock(full_name="Test User", status="active", ulp_id="user_ulp_id")
    keyring = Mock(
        registry_type="nfc",
        registry_id="123456",
        ulp_user="user_ulp_id",
    )
    keyring_2 = Mock(
        registry_type="fingerprint",
        registry_id="2",
        ulp_user="user_ulp_id",
    )
    ufp.api.bootstrap.ulp_users.as_list = Mock(return_value=[ulp_user])
    ufp.api.bootstrap.keyrings.as_list = Mock(return_value=[keyring, keyring_2])

    await init_entry(hass, ufp, [doorbell])

    camera_entry = entity_registry.async_get("event.test_camera_doorbell")

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_USER_KEYRING_INFO,
        {ATTR_DEVICE_ID: camera_entry.device_id},
        blocking=True,
        return_response=True,
    )

    assert response == {
        "users": [
            {
                KEYRINGS_USER_FULL_NAME: "Test User",
                "keys": [
                    {
                        KEYRINGS_KEY_TYPE: "nfc",
                        KEYRINGS_KEY_TYPE_ID_NFC: "123456",
                    },
                    {
                        KEYRINGS_KEY_TYPE_ID_FINGERPRINT: "2",
                        KEYRINGS_KEY_TYPE: "fingerprint",
                    },
                ],
                KEYRINGS_USER_STATUS: "active",
                KEYRINGS_ULP_ID: "user_ulp_id",
            },
        ],
    }


async def test_get_user_keyring_info_no_users(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """Test get_user_keyring_info service with no users."""

    ufp.api.bootstrap.ulp_users.as_list = Mock(return_value=[])
    ufp.api.bootstrap.keyrings.as_list = Mock(return_value=[])

    await init_entry(hass, ufp, [doorbell])

    camera_entry = entity_registry.async_get("event.test_camera_doorbell")

    with pytest.raises(
        HomeAssistantError, match="No users found, please check Protect permissions"
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_USER_KEYRING_INFO,
            {ATTR_DEVICE_ID: camera_entry.device_id},
            blocking=True,
            return_response=True,
        )


# --- PTZ Preset Service Tests ---


def _make_presets() -> list[PTZPreset]:
    """Create mock PTZ presets."""
    return [
        PTZPreset(
            id="preset1",
            name="Preset 1",
            slot=0,
            ptz={"pan": 100, "tilt": 50, "zoom": 0},
        ),
        PTZPreset(
            id="preset2",
            name="Preset 2",
            slot=1,
            ptz={"pan": 200, "tilt": 100, "zoom": 50},
        ),
    ]


async def test_ptz_goto_preset(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    ptz_camera: Camera,
) -> None:
    """Test ptz_goto_preset service with a named preset."""
    ptz_camera.get_ptz_presets.return_value = _make_presets()
    ptz_camera.get_ptz_patrols.return_value = []
    await init_entry(hass, ufp, [ptz_camera])

    camera_entry = entity_registry.async_get(
        "camera.ptz_camera_high_resolution_channel"
    )

    public = ufp.api.public_bootstrap.cameras[ptz_camera.id]
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PTZ_GOTO_PRESET,
        {ATTR_DEVICE_ID: camera_entry.device_id, ATTR_PRESET: "Preset 1"},
        blocking=True,
    )
    public.ptz_goto_preset.assert_awaited_once_with(slot=0)


async def test_ptz_goto_preset_home(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    ptz_camera: Camera,
) -> None:
    """Test ptz_goto_preset service with home preset."""
    ptz_camera.get_ptz_patrols.return_value = []
    await init_entry(hass, ufp, [ptz_camera])

    camera_entry = entity_registry.async_get(
        "camera.ptz_camera_high_resolution_channel"
    )

    public = ufp.api.public_bootstrap.cameras[ptz_camera.id]
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PTZ_GOTO_PRESET,
        {ATTR_DEVICE_ID: camera_entry.device_id, ATTR_PRESET: "Home"},
        blocking=True,
    )
    public.ptz_goto_preset.assert_awaited_once_with(slot=-1)


async def test_ptz_goto_preset_not_found(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    ptz_camera: Camera,
) -> None:
    """Test ptz_goto_preset service with non-existent preset."""
    ptz_camera.get_ptz_presets.return_value = []
    ptz_camera.get_ptz_patrols.return_value = []
    await init_entry(hass, ufp, [ptz_camera])

    camera_entry = entity_registry.async_get(
        "camera.ptz_camera_high_resolution_channel"
    )

    with pytest.raises(ServiceValidationError, match="Could not find PTZ preset"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PTZ_GOTO_PRESET,
            {
                ATTR_DEVICE_ID: camera_entry.device_id,
                ATTR_PRESET: "Does Not Exist",
            },
            blocking=True,
        )


async def test_ptz_goto_preset_not_ptz_camera(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    doorbell: Camera,
) -> None:
    """Test ptz_goto_preset service on a non-PTZ camera."""
    await init_entry(hass, ufp, [doorbell])

    camera_entry = entity_registry.async_get("event.test_camera_doorbell")

    with pytest.raises(ServiceValidationError, match="does not support PTZ"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PTZ_GOTO_PRESET,
            {ATTR_DEVICE_ID: camera_entry.device_id, ATTR_PRESET: "Home"},
            blocking=True,
        )


async def test_ptz_goto_preset_client_error(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    ptz_camera: Camera,
) -> None:
    """Test ptz_goto_preset service when get_ptz_presets raises ClientError."""
    ptz_camera.get_ptz_presets.side_effect = ClientError("Connection failed")
    ptz_camera.get_ptz_patrols.return_value = []
    await init_entry(hass, ufp, [ptz_camera])

    camera_entry = entity_registry.async_get(
        "camera.ptz_camera_high_resolution_channel"
    )

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PTZ_GOTO_PRESET,
            {ATTR_DEVICE_ID: camera_entry.device_id, ATTR_PRESET: "Preset 1"},
            blocking=True,
        )


async def test_ptz_goto_preset_public_client_error(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    ptz_camera: Camera,
) -> None:
    """Test ptz_goto_preset service when ptz_goto_preset raises ClientError."""
    ptz_camera.get_ptz_presets.return_value = _make_presets()
    ptz_camera.get_ptz_patrols.return_value = []
    await init_entry(hass, ufp, [ptz_camera])

    camera_entry = entity_registry.async_get(
        "camera.ptz_camera_high_resolution_channel"
    )

    public = ufp.api.public_bootstrap.cameras[ptz_camera.id]
    public.ptz_goto_preset.side_effect = ClientError("Connection failed")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PTZ_GOTO_PRESET,
            {ATTR_DEVICE_ID: camera_entry.device_id, ATTR_PRESET: "Preset 1"},
            blocking=True,
        )


async def test_ptz_goto_home_preset_client_error(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    ptz_camera: Camera,
) -> None:
    """Test ptz_goto_preset with home preset when it raises ClientError."""
    ptz_camera.get_ptz_patrols.return_value = []
    await init_entry(hass, ufp, [ptz_camera])

    camera_entry = entity_registry.async_get(
        "camera.ptz_camera_high_resolution_channel"
    )

    public = ufp.api.public_bootstrap.cameras[ptz_camera.id]
    public.ptz_goto_preset.side_effect = ClientError("Connection failed")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PTZ_GOTO_PRESET,
            {ATTR_DEVICE_ID: camera_entry.device_id, ATTR_PRESET: "Home"},
            blocking=True,
        )


async def test_ptz_goto_preset_no_public_camera(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    ptz_camera: Camera,
) -> None:
    """Test ptz_goto_preset raises when the camera is missing from the public API."""
    await init_entry(hass, ufp, [ptz_camera])

    camera_entry = entity_registry.async_get(
        "camera.ptz_camera_high_resolution_channel"
    )

    ufp.api.public_bootstrap.cameras = {}
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PTZ_GOTO_PRESET,
            {ATTR_DEVICE_ID: camera_entry.device_id, ATTR_PRESET: "Home"},
            blocking=True,
        )
    assert exc_info.value.translation_key == "device_not_available"


async def test_public_only_action_rejected(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """Actions require full access; a public-only device raises cleanly."""
    await setup_public_only()
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, UNIFI_MAC), ufp_public_only.entry.entry_id
    )
    assert device is not None

    with pytest.raises(HomeAssistantError, match="requires a local user"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_DOORBELL_TEXT,
            {ATTR_DEVICE_ID: device.id, ATTR_MESSAGE: "Test Message"},
            blocking=True,
        )


async def test_trigger_alarm_webhook(
    hass: HomeAssistant,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """Test trigger_alarm_webhook, which also works on an API-key-only entry."""
    await setup_public_only()
    ufp_public_only.api.send_alarm_webhook_public = AsyncMock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_TRIGGER_ALARM_WEBHOOK,
        {
            ATTR_CONFIG_ENTRY_ID: ufp_public_only.entry.entry_id,
            ATTR_TRIGGER_ID: "test-trigger",
        },
        blocking=True,
    )
    ufp_public_only.api.send_alarm_webhook_public.assert_awaited_once_with(
        "test-trigger"
    )


@pytest.mark.usefixtures("device")
async def test_trigger_alarm_webhook_error(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> None:
    """Test trigger_alarm_webhook reports Protect errors."""
    ufp.api.send_alarm_webhook_public = AsyncMock(side_effect=BadRequest("400"))

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TRIGGER_ALARM_WEBHOOK,
            {ATTR_CONFIG_ENTRY_ID: ufp.entry.entry_id, ATTR_TRIGGER_ID: "test-trigger"},
            blocking=True,
        )
    assert exc_info.value.translation_key == "command_error"
    assert exc_info.value.translation_placeholders == {"error": "400"}


@pytest.mark.usefixtures("device")
async def test_trigger_alarm_webhook_empty_trigger_id(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> None:
    """Test trigger_alarm_webhook rejects an empty trigger ID."""
    ufp.api.send_alarm_webhook_public = AsyncMock()

    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TRIGGER_ALARM_WEBHOOK,
            {ATTR_CONFIG_ENTRY_ID: ufp.entry.entry_id, ATTR_TRIGGER_ID: ""},
            blocking=True,
        )
    ufp.api.send_alarm_webhook_public.assert_not_awaited()


@pytest.mark.usefixtures("device")
async def test_trigger_alarm_webhook_non_admin(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    hass_read_only_user: MockUser,
) -> None:
    """Test trigger_alarm_webhook rejects non-admin callers."""
    ufp.api.send_alarm_webhook_public = AsyncMock()

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TRIGGER_ALARM_WEBHOOK,
            {ATTR_CONFIG_ENTRY_ID: ufp.entry.entry_id, ATTR_TRIGGER_ID: "test-trigger"},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )
    ufp.api.send_alarm_webhook_public.assert_not_awaited()
