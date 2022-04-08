"""Test ZHA select entities."""

import pytest
from zigpy.const import SIG_EP_PROFILE
import zigpy.profiles.zha as zha
import zigpy.zcl.clusters.general as general
import zigpy.zcl.clusters.security as security

from homeassistant.const import ENTITY_CATEGORY_CONFIG, STATE_UNKNOWN, Platform
from homeassistant.helpers import entity_registry as er, restore_state
from homeassistant.util import dt as dt_util

from .common import find_entity_id
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_TYPE


@pytest.fixture
async def siren(hass, zigpy_device_mock, zha_device_joined_restored):
    """Siren fixture."""

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [general.Basic.cluster_id, security.IasWd.cluster_id],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.IAS_WARNING_DEVICE,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
    )

    zha_device = await zha_device_joined_restored(zigpy_device)
    return zha_device, zigpy_device.endpoints[1].ias_wd


@pytest.fixture
def core_rs(hass_storage):
    """Core.restore_state fixture."""

    def _storage(entity_id, state):
        now = dt_util.utcnow().isoformat()

        hass_storage[restore_state.STORAGE_KEY] = {
            "version": restore_state.STORAGE_VERSION,
            "key": restore_state.STORAGE_KEY,
            "data": [
                {
                    "state": {
                        "entity_id": entity_id,
                        "state": str(state),
                        "last_changed": now,
                        "last_updated": now,
                        "context": {
                            "id": "3c2243ff5f30447eb12e7348cfd5b8ff",
                            "user_id": None,
                        },
                    },
                    "last_seen": now,
                }
            ],
        }
        return

    return _storage


async def test_select(hass, siren):
    """Test zha select platform."""

    entity_registry = er.async_get(hass)
    zha_device, cluster = siren
    assert cluster is not None
    select_name = security.IasWd.Warning.WarningMode.__name__
    entity_id = await find_entity_id(
        Platform.SELECT,
        zha_device,
        hass,
        qualifier=select_name.lower(),
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes["options"] == [
        "Stop",
        "Burglar",
        "Fire",
        "Emergency",
        "Police Panic",
        "Fire Panic",
        "Emergency Panic",
    ]

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry
    assert entity_entry.entity_category == ENTITY_CATEGORY_CONFIG

    # Test select option with string value
    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": entity_id,
            "option": security.IasWd.Warning.WarningMode.Burglar.name,
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state
    assert state.state == security.IasWd.Warning.WarningMode.Burglar.name


async def test_select_restore_state(
    hass,
    zigpy_device_mock,
    core_rs,
    zha_device_restored,
):
    """Test zha select entity restore state."""

    entity_id = "select.fakemanufacturer_fakemodel_e769900a_ias_wd_warningmode"
    core_rs(entity_id, state="Burglar")

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [general.Basic.cluster_id, security.IasWd.cluster_id],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.IAS_WARNING_DEVICE,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
    )

    zha_device = await zha_device_restored(zigpy_device)
    cluster = zigpy_device.endpoints[1].ias_wd
    assert cluster is not None
    select_name = security.IasWd.Warning.WarningMode.__name__
    entity_id = await find_entity_id(
        Platform.SELECT,
        zha_device,
        hass,
        qualifier=select_name.lower(),
    )

    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state
    assert state.state == security.IasWd.Warning.WarningMode.Burglar.name
