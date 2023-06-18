"""Tests for the Risco alarm control panel device."""
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_DOMAIN,
    AlarmControlPanelEntityFeature,
)
from homeassistant.components.risco import CannotConnectError, UnauthorizedError
from homeassistant.components.risco.const import DOMAIN
from homeassistant.const import (
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_CUSTOM_BYPASS,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_DISARM,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from .util import TEST_SITE_UUID

FIRST_CLOUD_ENTITY_ID = "alarm_control_panel.risco_test_site_name_partition_0"
SECOND_CLOUD_ENTITY_ID = "alarm_control_panel.risco_test_site_name_partition_1"

FIRST_LOCAL_ENTITY_ID = "alarm_control_panel.name_0"
SECOND_LOCAL_ENTITY_ID = "alarm_control_panel.name_1"

CODES_REQUIRED_OPTIONS = {"code_arm_required": True, "code_disarm_required": True}
TEST_RISCO_TO_HA = {
    "arm": STATE_ALARM_ARMED_AWAY,
    "partial_arm": STATE_ALARM_ARMED_HOME,
    "A": STATE_ALARM_ARMED_HOME,
    "B": STATE_ALARM_ARMED_HOME,
    "C": STATE_ALARM_ARMED_NIGHT,
    "D": STATE_ALARM_ARMED_NIGHT,
}
TEST_FULL_RISCO_TO_HA = {
    **TEST_RISCO_TO_HA,
    "D": STATE_ALARM_ARMED_CUSTOM_BYPASS,
}
TEST_HA_TO_RISCO = {
    STATE_ALARM_ARMED_AWAY: "arm",
    STATE_ALARM_ARMED_HOME: "partial_arm",
    STATE_ALARM_ARMED_NIGHT: "C",
}
TEST_FULL_HA_TO_RISCO = {
    **TEST_HA_TO_RISCO,
    STATE_ALARM_ARMED_CUSTOM_BYPASS: "D",
}
CUSTOM_MAPPING_OPTIONS = {
    "risco_states_to_ha": TEST_RISCO_TO_HA,
    "ha_states_to_risco": TEST_HA_TO_RISCO,
}

FULL_CUSTOM_MAPPING = {
    "risco_states_to_ha": TEST_FULL_RISCO_TO_HA,
    "ha_states_to_risco": TEST_FULL_HA_TO_RISCO,
}

EXPECTED_FEATURES = (
    AlarmControlPanelEntityFeature.ARM_AWAY
    | AlarmControlPanelEntityFeature.ARM_HOME
    | AlarmControlPanelEntityFeature.ARM_NIGHT
)


def _partition_mock():
    return MagicMock(
        triggered=False,
        arming=False,
        armed=False,
        disarmed=False,
        partially_armed=False,
    )


@pytest.fixture
def two_part_cloud_alarm():
    """Fixture to mock alarm with two partitions."""
    partition_mocks = {0: _partition_mock(), 1: _partition_mock()}
    alarm_mock = MagicMock()
    with patch.object(
        partition_mocks[0], "id", new_callable=PropertyMock(return_value=0)
    ), patch.object(
        partition_mocks[1], "id", new_callable=PropertyMock(return_value=1)
    ), patch.object(
        alarm_mock,
        "partitions",
        new_callable=PropertyMock(return_value=partition_mocks),
    ), patch(
        "homeassistant.components.risco.RiscoCloud.get_state",
        return_value=alarm_mock,
    ):
        yield partition_mocks


@pytest.fixture
def two_part_local_alarm():
    """Fixture to mock alarm with two partitions."""
    partition_mocks = {0: _partition_mock(), 1: _partition_mock()}
    with patch.object(
        partition_mocks[0], "id", new_callable=PropertyMock(return_value=0)
    ), patch.object(
        partition_mocks[0], "name", new_callable=PropertyMock(return_value="Name 0")
    ), patch.object(
        partition_mocks[1], "id", new_callable=PropertyMock(return_value=1)
    ), patch.object(
        partition_mocks[1], "name", new_callable=PropertyMock(return_value="Name 1")
    ), patch(
        "homeassistant.components.risco.RiscoLocal.zones",
        new_callable=PropertyMock(return_value={}),
    ), patch(
        "homeassistant.components.risco.RiscoLocal.partitions",
        new_callable=PropertyMock(return_value=partition_mocks),
    ):
        yield partition_mocks


@pytest.mark.parametrize("exception", [CannotConnectError, UnauthorizedError])
async def test_error_on_login(
    hass: HomeAssistant, login_with_error, cloud_config_entry
) -> None:
    """Test error on login."""
    await hass.config_entries.async_setup(cloud_config_entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    assert not registry.async_is_registered(FIRST_CLOUD_ENTITY_ID)
    assert not registry.async_is_registered(SECOND_CLOUD_ENTITY_ID)


async def test_cloud_setup(
    hass: HomeAssistant, two_part_cloud_alarm, setup_risco_cloud
) -> None:
    """Test entity setup."""
    registry = er.async_get(hass)
    assert registry.async_is_registered(FIRST_CLOUD_ENTITY_ID)
    assert registry.async_is_registered(SECOND_CLOUD_ENTITY_ID)

    registry = dr.async_get(hass)
    device = registry.async_get_device({(DOMAIN, TEST_SITE_UUID + "_0")})
    assert device is not None
    assert device.manufacturer == "Risco"

    device = registry.async_get_device({(DOMAIN, TEST_SITE_UUID + "_1")})
    assert device is not None
    assert device.manufacturer == "Risco"


async def _check_cloud_state(
    hass, partitions, property, state, entity_id, partition_id
):
    with patch.object(partitions[partition_id], property, return_value=True):
        await async_update_entity(hass, entity_id)
        await hass.async_block_till_done()

        assert hass.states.get(entity_id).state == state


@pytest.mark.parametrize("options", [CUSTOM_MAPPING_OPTIONS])
async def test_cloud_states(
    hass: HomeAssistant, two_part_cloud_alarm, setup_risco_cloud
) -> None:
    """Test the various alarm states."""
    assert hass.states.get(FIRST_CLOUD_ENTITY_ID).state == STATE_UNKNOWN
    for partition_id, entity_id in {
        0: FIRST_CLOUD_ENTITY_ID,
        1: SECOND_CLOUD_ENTITY_ID,
    }.items():
        await _check_cloud_state(
            hass,
            two_part_cloud_alarm,
            "triggered",
            STATE_ALARM_TRIGGERED,
            entity_id,
            partition_id,
        )
        await _check_cloud_state(
            hass,
            two_part_cloud_alarm,
            "arming",
            STATE_ALARM_ARMING,
            entity_id,
            partition_id,
        )
        await _check_cloud_state(
            hass,
            two_part_cloud_alarm,
            "armed",
            STATE_ALARM_ARMED_AWAY,
            entity_id,
            partition_id,
        )
        await _check_cloud_state(
            hass,
            two_part_cloud_alarm,
            "partially_armed",
            STATE_ALARM_ARMED_HOME,
            entity_id,
            partition_id,
        )
        await _check_cloud_state(
            hass,
            two_part_cloud_alarm,
            "disarmed",
            STATE_ALARM_DISARMED,
            entity_id,
            partition_id,
        )

        groups = {"A": False, "B": False, "C": True, "D": False}
        with patch.object(
            two_part_cloud_alarm[partition_id],
            "groups",
            new_callable=PropertyMock(return_value=groups),
        ):
            await _check_cloud_state(
                hass,
                two_part_cloud_alarm,
                "partially_armed",
                STATE_ALARM_ARMED_NIGHT,
                entity_id,
                partition_id,
            )


async def _call_alarm_service(hass, service, entity_id, **kwargs):
    data = {"entity_id": entity_id, **kwargs}

    await hass.services.async_call(
        ALARM_DOMAIN, service, service_data=data, blocking=True
    )


async def _test_cloud_service_call(
    hass, service, method, entity_id, partition_id, *args, **kwargs
):
    with patch(f"homeassistant.components.risco.RiscoCloud.{method}") as set_mock:
        await _call_alarm_service(hass, service, entity_id, **kwargs)
        set_mock.assert_awaited_once_with(partition_id, *args)


async def _test_cloud_no_service_call(
    hass, service, method, entity_id, partition_id, **kwargs
):
    with patch(f"homeassistant.components.risco.RiscoCloud.{method}") as set_mock:
        await _call_alarm_service(hass, service, entity_id, **kwargs)
        set_mock.assert_not_awaited()


@pytest.mark.parametrize("options", [CUSTOM_MAPPING_OPTIONS])
async def test_cloud_sets_custom_mapping(
    hass: HomeAssistant, two_part_cloud_alarm, setup_risco_cloud
) -> None:
    """Test settings the various modes when mapping some states."""
    registry = er.async_get(hass)
    entity = registry.async_get(FIRST_CLOUD_ENTITY_ID)
    assert entity.supported_features == EXPECTED_FEATURES

    await _test_cloud_service_call(
        hass, SERVICE_ALARM_DISARM, "disarm", FIRST_CLOUD_ENTITY_ID, 0
    )
    await _test_cloud_service_call(
        hass, SERVICE_ALARM_DISARM, "disarm", SECOND_CLOUD_ENTITY_ID, 1
    )
    await _test_cloud_service_call(
        hass, SERVICE_ALARM_ARM_AWAY, "arm", FIRST_CLOUD_ENTITY_ID, 0
    )
    await _test_cloud_service_call(
        hass, SERVICE_ALARM_ARM_AWAY, "arm", SECOND_CLOUD_ENTITY_ID, 1
    )
    await _test_cloud_service_call(
        hass, SERVICE_ALARM_ARM_HOME, "partial_arm", FIRST_CLOUD_ENTITY_ID, 0
    )
    await _test_cloud_service_call(
        hass, SERVICE_ALARM_ARM_HOME, "partial_arm", SECOND_CLOUD_ENTITY_ID, 1
    )
    await _test_cloud_service_call(
        hass, SERVICE_ALARM_ARM_NIGHT, "group_arm", FIRST_CLOUD_ENTITY_ID, 0, "C"
    )
    await _test_cloud_service_call(
        hass, SERVICE_ALARM_ARM_NIGHT, "group_arm", SECOND_CLOUD_ENTITY_ID, 1, "C"
    )


@pytest.mark.parametrize("options", [FULL_CUSTOM_MAPPING])
async def test_cloud_sets_full_custom_mapping(
    hass: HomeAssistant, two_part_cloud_alarm, setup_risco_cloud
) -> None:
    """Test settings the various modes when mapping all states."""
    registry = er.async_get(hass)
    entity = registry.async_get(FIRST_CLOUD_ENTITY_ID)
    assert (
        entity.supported_features
        == EXPECTED_FEATURES | AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS
    )

    await _test_cloud_service_call(
        hass, SERVICE_ALARM_DISARM, "disarm", FIRST_CLOUD_ENTITY_ID, 0
    )
    await _test_cloud_service_call(
        hass, SERVICE_ALARM_DISARM, "disarm", SECOND_CLOUD_ENTITY_ID, 1
    )
    await _test_cloud_service_call(
        hass, SERVICE_ALARM_ARM_AWAY, "arm", FIRST_CLOUD_ENTITY_ID, 0
    )
    await _test_cloud_service_call(
        hass, SERVICE_ALARM_ARM_AWAY, "arm", SECOND_CLOUD_ENTITY_ID, 1
    )
    await _test_cloud_service_call(
        hass, SERVICE_ALARM_ARM_HOME, "partial_arm", FIRST_CLOUD_ENTITY_ID, 0
    )
    await _test_cloud_service_call(
        hass, SERVICE_ALARM_ARM_HOME, "partial_arm", SECOND_CLOUD_ENTITY_ID, 1
    )
    await _test_cloud_service_call(
        hass, SERVICE_ALARM_ARM_NIGHT, "group_arm", FIRST_CLOUD_ENTITY_ID, 0, "C"
    )
    await _test_cloud_service_call(
        hass, SERVICE_ALARM_ARM_NIGHT, "group_arm", SECOND_CLOUD_ENTITY_ID, 1, "C"
    )
    await _test_cloud_service_call(
        hass,
        SERVICE_ALARM_ARM_CUSTOM_BYPASS,
        "group_arm",
        FIRST_CLOUD_ENTITY_ID,
        0,
        "D",
    )
    await _test_cloud_service_call(
        hass,
        SERVICE_ALARM_ARM_CUSTOM_BYPASS,
        "group_arm",
        SECOND_CLOUD_ENTITY_ID,
        1,
        "D",
    )


@pytest.mark.parametrize(
    "options", [{**CUSTOM_MAPPING_OPTIONS, **CODES_REQUIRED_OPTIONS}]
)
async def test_cloud_sets_with_correct_code(
    hass: HomeAssistant, two_part_cloud_alarm, setup_risco_cloud
) -> None:
    """Test settings the various modes when code is required."""
    code = {"code": 1234}
    await _test_cloud_service_call(
        hass, SERVICE_ALARM_DISARM, "disarm", FIRST_CLOUD_ENTITY_ID, 0, **code
    )
    await _test_cloud_service_call(
        hass, SERVICE_ALARM_DISARM, "disarm", SECOND_CLOUD_ENTITY_ID, 1, **code
    )
    await _test_cloud_service_call(
        hass, SERVICE_ALARM_ARM_AWAY, "arm", FIRST_CLOUD_ENTITY_ID, 0, **code
    )
    await _test_cloud_service_call(
        hass, SERVICE_ALARM_ARM_AWAY, "arm", SECOND_CLOUD_ENTITY_ID, 1, **code
    )
    await _test_cloud_service_call(
        hass, SERVICE_ALARM_ARM_HOME, "partial_arm", FIRST_CLOUD_ENTITY_ID, 0, **code
    )
    await _test_cloud_service_call(
        hass, SERVICE_ALARM_ARM_HOME, "partial_arm", SECOND_CLOUD_ENTITY_ID, 1, **code
    )
    await _test_cloud_service_call(
        hass,
        SERVICE_ALARM_ARM_NIGHT,
        "group_arm",
        FIRST_CLOUD_ENTITY_ID,
        0,
        "C",
        **code,
    )
    await _test_cloud_service_call(
        hass,
        SERVICE_ALARM_ARM_NIGHT,
        "group_arm",
        SECOND_CLOUD_ENTITY_ID,
        1,
        "C",
        **code,
    )
    with pytest.raises(HomeAssistantError):
        await _test_cloud_no_service_call(
            hass,
            SERVICE_ALARM_ARM_CUSTOM_BYPASS,
            "partial_arm",
            FIRST_CLOUD_ENTITY_ID,
            0,
            **code,
        )
    with pytest.raises(HomeAssistantError):
        await _test_cloud_no_service_call(
            hass,
            SERVICE_ALARM_ARM_CUSTOM_BYPASS,
            "partial_arm",
            SECOND_CLOUD_ENTITY_ID,
            1,
            **code,
        )


@pytest.mark.parametrize(
    "options", [{**CUSTOM_MAPPING_OPTIONS, **CODES_REQUIRED_OPTIONS}]
)
async def test_cloud_sets_with_incorrect_code(
    hass: HomeAssistant, two_part_cloud_alarm, setup_risco_cloud
) -> None:
    """Test settings the various modes when code is required and incorrect."""
    code = {"code": 4321}
    await _test_cloud_no_service_call(
        hass, SERVICE_ALARM_DISARM, "disarm", FIRST_CLOUD_ENTITY_ID, 0, **code
    )
    await _test_cloud_no_service_call(
        hass, SERVICE_ALARM_DISARM, "disarm", SECOND_CLOUD_ENTITY_ID, 1, **code
    )
    await _test_cloud_no_service_call(
        hass, SERVICE_ALARM_ARM_AWAY, "arm", FIRST_CLOUD_ENTITY_ID, 0, **code
    )
    await _test_cloud_no_service_call(
        hass, SERVICE_ALARM_ARM_AWAY, "arm", SECOND_CLOUD_ENTITY_ID, 1, **code
    )
    await _test_cloud_no_service_call(
        hass, SERVICE_ALARM_ARM_HOME, "partial_arm", FIRST_CLOUD_ENTITY_ID, 0, **code
    )
    await _test_cloud_no_service_call(
        hass, SERVICE_ALARM_ARM_HOME, "partial_arm", SECOND_CLOUD_ENTITY_ID, 1, **code
    )
    await _test_cloud_no_service_call(
        hass, SERVICE_ALARM_ARM_NIGHT, "group_arm", FIRST_CLOUD_ENTITY_ID, 0, **code
    )
    await _test_cloud_no_service_call(
        hass, SERVICE_ALARM_ARM_NIGHT, "group_arm", SECOND_CLOUD_ENTITY_ID, 1, **code
    )
    with pytest.raises(HomeAssistantError):
        await _test_cloud_no_service_call(
            hass,
            SERVICE_ALARM_ARM_CUSTOM_BYPASS,
            "partial_arm",
            FIRST_CLOUD_ENTITY_ID,
            0,
            **code,
        )
    with pytest.raises(HomeAssistantError):
        await _test_cloud_no_service_call(
            hass,
            SERVICE_ALARM_ARM_CUSTOM_BYPASS,
            "partial_arm",
            SECOND_CLOUD_ENTITY_ID,
            1,
            **code,
        )


@pytest.mark.parametrize("exception", [CannotConnectError, UnauthorizedError])
async def test_error_on_connect(
    hass: HomeAssistant, connect_with_error, local_config_entry
) -> None:
    """Test error on connect."""
    await hass.config_entries.async_setup(local_config_entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    assert not registry.async_is_registered(FIRST_LOCAL_ENTITY_ID)
    assert not registry.async_is_registered(SECOND_LOCAL_ENTITY_ID)


async def test_local_setup(
    hass: HomeAssistant, two_part_local_alarm, setup_risco_local
) -> None:
    """Test entity setup."""
    registry = er.async_get(hass)
    assert registry.async_is_registered(FIRST_LOCAL_ENTITY_ID)
    assert registry.async_is_registered(SECOND_LOCAL_ENTITY_ID)

    registry = dr.async_get(hass)
    device = registry.async_get_device({(DOMAIN, TEST_SITE_UUID + "_0_local")})
    assert device is not None
    assert device.manufacturer == "Risco"

    device = registry.async_get_device({(DOMAIN, TEST_SITE_UUID + "_1_local")})
    assert device is not None
    assert device.manufacturer == "Risco"
    with patch("homeassistant.components.risco.RiscoLocal.disconnect") as mock_close:
        await hass.config_entries.async_unload(setup_risco_local.entry_id)
        mock_close.assert_awaited_once()


async def _check_local_state(
    hass, partitions, property, state, entity_id, partition_id, callback
):
    with patch.object(partitions[partition_id], property, return_value=True):
        await callback(partition_id, partitions[partition_id])

    assert hass.states.get(entity_id).state == state


@pytest.fixture
def _mock_partition_handler():
    with patch(
        "homeassistant.components.risco.RiscoLocal.add_partition_handler"
    ) as mock:
        yield mock


@pytest.mark.parametrize("options", [CUSTOM_MAPPING_OPTIONS])
async def test_local_states(
    hass: HomeAssistant,
    two_part_local_alarm,
    _mock_partition_handler,
    setup_risco_local,
) -> None:
    """Test the various alarm states."""
    callback = _mock_partition_handler.call_args.args[0]

    assert callback is not None

    assert hass.states.get(FIRST_LOCAL_ENTITY_ID).state == STATE_UNKNOWN
    for partition_id, entity_id in {
        0: FIRST_LOCAL_ENTITY_ID,
        1: SECOND_LOCAL_ENTITY_ID,
    }.items():
        await _check_local_state(
            hass,
            two_part_local_alarm,
            "triggered",
            STATE_ALARM_TRIGGERED,
            entity_id,
            partition_id,
            callback,
        )
        await _check_local_state(
            hass,
            two_part_local_alarm,
            "arming",
            STATE_ALARM_ARMING,
            entity_id,
            partition_id,
            callback,
        )
        await _check_local_state(
            hass,
            two_part_local_alarm,
            "armed",
            STATE_ALARM_ARMED_AWAY,
            entity_id,
            partition_id,
            callback,
        )
        await _check_local_state(
            hass,
            two_part_local_alarm,
            "partially_armed",
            STATE_ALARM_ARMED_HOME,
            entity_id,
            partition_id,
            callback,
        )
        await _check_local_state(
            hass,
            two_part_local_alarm,
            "disarmed",
            STATE_ALARM_DISARMED,
            entity_id,
            partition_id,
            callback,
        )

        groups = {"A": False, "B": False, "C": True, "D": False}
        with patch.object(
            two_part_local_alarm[partition_id],
            "groups",
            new_callable=PropertyMock(return_value=groups),
        ):
            await _check_local_state(
                hass,
                two_part_local_alarm,
                "partially_armed",
                STATE_ALARM_ARMED_NIGHT,
                entity_id,
                partition_id,
                callback,
            )


async def _test_local_service_call(
    hass, service, method, entity_id, partition, *args, **kwargs
):
    with patch.object(partition, method, AsyncMock()) as set_mock:
        await _call_alarm_service(hass, service, entity_id, **kwargs)
        set_mock.assert_awaited_once_with(*args)


async def _test_local_no_service_call(
    hass, service, method, entity_id, partition, **kwargs
):
    with patch.object(partition, method, AsyncMock()) as set_mock:
        await _call_alarm_service(hass, service, entity_id, **kwargs)
        set_mock.assert_not_awaited()


@pytest.mark.parametrize("options", [CUSTOM_MAPPING_OPTIONS])
async def test_local_sets_custom_mapping(
    hass: HomeAssistant, two_part_local_alarm, setup_risco_local
) -> None:
    """Test settings the various modes when mapping some states."""
    registry = er.async_get(hass)
    entity = registry.async_get(FIRST_LOCAL_ENTITY_ID)
    assert entity.supported_features == EXPECTED_FEATURES

    await _test_local_service_call(
        hass,
        SERVICE_ALARM_DISARM,
        "disarm",
        FIRST_LOCAL_ENTITY_ID,
        two_part_local_alarm[0],
    )
    await _test_local_service_call(
        hass,
        SERVICE_ALARM_DISARM,
        "disarm",
        SECOND_LOCAL_ENTITY_ID,
        two_part_local_alarm[1],
    )
    await _test_local_service_call(
        hass,
        SERVICE_ALARM_ARM_AWAY,
        "arm",
        FIRST_LOCAL_ENTITY_ID,
        two_part_local_alarm[0],
    )
    await _test_local_service_call(
        hass,
        SERVICE_ALARM_ARM_AWAY,
        "arm",
        SECOND_LOCAL_ENTITY_ID,
        two_part_local_alarm[1],
    )
    await _test_local_service_call(
        hass,
        SERVICE_ALARM_ARM_HOME,
        "partial_arm",
        FIRST_LOCAL_ENTITY_ID,
        two_part_local_alarm[0],
    )
    await _test_local_service_call(
        hass,
        SERVICE_ALARM_ARM_HOME,
        "partial_arm",
        SECOND_LOCAL_ENTITY_ID,
        two_part_local_alarm[1],
    )
    await _test_local_service_call(
        hass,
        SERVICE_ALARM_ARM_NIGHT,
        "group_arm",
        FIRST_LOCAL_ENTITY_ID,
        two_part_local_alarm[0],
        "C",
    )
    await _test_local_service_call(
        hass,
        SERVICE_ALARM_ARM_NIGHT,
        "group_arm",
        SECOND_LOCAL_ENTITY_ID,
        two_part_local_alarm[1],
        "C",
    )


@pytest.mark.parametrize("options", [FULL_CUSTOM_MAPPING])
async def test_local_sets_full_custom_mapping(
    hass: HomeAssistant, two_part_local_alarm, setup_risco_local
) -> None:
    """Test settings the various modes when mapping all states."""
    registry = er.async_get(hass)
    entity = registry.async_get(FIRST_LOCAL_ENTITY_ID)
    assert (
        entity.supported_features
        == EXPECTED_FEATURES | AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS
    )

    await _test_local_service_call(
        hass,
        SERVICE_ALARM_DISARM,
        "disarm",
        FIRST_LOCAL_ENTITY_ID,
        two_part_local_alarm[0],
    )
    await _test_local_service_call(
        hass,
        SERVICE_ALARM_DISARM,
        "disarm",
        SECOND_LOCAL_ENTITY_ID,
        two_part_local_alarm[1],
    )
    await _test_local_service_call(
        hass,
        SERVICE_ALARM_ARM_AWAY,
        "arm",
        FIRST_LOCAL_ENTITY_ID,
        two_part_local_alarm[0],
    )
    await _test_local_service_call(
        hass,
        SERVICE_ALARM_ARM_AWAY,
        "arm",
        SECOND_LOCAL_ENTITY_ID,
        two_part_local_alarm[1],
    )
    await _test_local_service_call(
        hass,
        SERVICE_ALARM_ARM_HOME,
        "partial_arm",
        FIRST_LOCAL_ENTITY_ID,
        two_part_local_alarm[0],
    )
    await _test_local_service_call(
        hass,
        SERVICE_ALARM_ARM_HOME,
        "partial_arm",
        SECOND_LOCAL_ENTITY_ID,
        two_part_local_alarm[1],
    )
    await _test_local_service_call(
        hass,
        SERVICE_ALARM_ARM_NIGHT,
        "group_arm",
        FIRST_LOCAL_ENTITY_ID,
        two_part_local_alarm[0],
        "C",
    )
    await _test_local_service_call(
        hass,
        SERVICE_ALARM_ARM_NIGHT,
        "group_arm",
        SECOND_LOCAL_ENTITY_ID,
        two_part_local_alarm[1],
        "C",
    )
    await _test_local_service_call(
        hass,
        SERVICE_ALARM_ARM_CUSTOM_BYPASS,
        "group_arm",
        FIRST_LOCAL_ENTITY_ID,
        two_part_local_alarm[0],
        "D",
    )
    await _test_local_service_call(
        hass,
        SERVICE_ALARM_ARM_CUSTOM_BYPASS,
        "group_arm",
        SECOND_LOCAL_ENTITY_ID,
        two_part_local_alarm[1],
        "D",
    )


@pytest.mark.parametrize(
    "options", [{**CUSTOM_MAPPING_OPTIONS, **CODES_REQUIRED_OPTIONS}]
)
async def test_local_sets_with_correct_code(
    hass: HomeAssistant, two_part_local_alarm, setup_risco_local
) -> None:
    """Test settings the various modes when code is required."""
    code = {"code": 1234}
    await _test_local_service_call(
        hass,
        SERVICE_ALARM_DISARM,
        "disarm",
        FIRST_LOCAL_ENTITY_ID,
        two_part_local_alarm[0],
        **code,
    )
    await _test_local_service_call(
        hass,
        SERVICE_ALARM_DISARM,
        "disarm",
        SECOND_LOCAL_ENTITY_ID,
        two_part_local_alarm[1],
        **code,
    )
    await _test_local_service_call(
        hass,
        SERVICE_ALARM_ARM_AWAY,
        "arm",
        FIRST_LOCAL_ENTITY_ID,
        two_part_local_alarm[0],
        **code,
    )
    await _test_local_service_call(
        hass,
        SERVICE_ALARM_ARM_AWAY,
        "arm",
        SECOND_LOCAL_ENTITY_ID,
        two_part_local_alarm[1],
        **code,
    )
    await _test_local_service_call(
        hass,
        SERVICE_ALARM_ARM_HOME,
        "partial_arm",
        FIRST_LOCAL_ENTITY_ID,
        two_part_local_alarm[0],
        **code,
    )
    await _test_local_service_call(
        hass,
        SERVICE_ALARM_ARM_HOME,
        "partial_arm",
        SECOND_LOCAL_ENTITY_ID,
        two_part_local_alarm[1],
        **code,
    )
    await _test_local_service_call(
        hass,
        SERVICE_ALARM_ARM_NIGHT,
        "group_arm",
        FIRST_LOCAL_ENTITY_ID,
        two_part_local_alarm[0],
        "C",
        **code,
    )
    await _test_local_service_call(
        hass,
        SERVICE_ALARM_ARM_NIGHT,
        "group_arm",
        SECOND_LOCAL_ENTITY_ID,
        two_part_local_alarm[1],
        "C",
        **code,
    )
    with pytest.raises(HomeAssistantError):
        await _test_local_no_service_call(
            hass,
            SERVICE_ALARM_ARM_CUSTOM_BYPASS,
            "partial_arm",
            FIRST_LOCAL_ENTITY_ID,
            two_part_local_alarm[0],
            **code,
        )
    with pytest.raises(HomeAssistantError):
        await _test_local_no_service_call(
            hass,
            SERVICE_ALARM_ARM_CUSTOM_BYPASS,
            "partial_arm",
            SECOND_LOCAL_ENTITY_ID,
            two_part_local_alarm[1],
            **code,
        )


@pytest.mark.parametrize(
    "options", [{**CUSTOM_MAPPING_OPTIONS, **CODES_REQUIRED_OPTIONS}]
)
async def test_local_sets_with_incorrect_code(
    hass: HomeAssistant, two_part_local_alarm, setup_risco_local
) -> None:
    """Test settings the various modes when code is required and incorrect."""
    code = {"code": 4321}
    await _test_local_no_service_call(
        hass,
        SERVICE_ALARM_DISARM,
        "disarm",
        FIRST_LOCAL_ENTITY_ID,
        two_part_local_alarm[0],
        **code,
    )
    await _test_local_no_service_call(
        hass,
        SERVICE_ALARM_DISARM,
        "disarm",
        SECOND_LOCAL_ENTITY_ID,
        two_part_local_alarm[1],
        **code,
    )
    await _test_local_no_service_call(
        hass,
        SERVICE_ALARM_ARM_AWAY,
        "arm",
        FIRST_LOCAL_ENTITY_ID,
        two_part_local_alarm[0],
        **code,
    )
    await _test_local_no_service_call(
        hass,
        SERVICE_ALARM_ARM_AWAY,
        "arm",
        SECOND_LOCAL_ENTITY_ID,
        two_part_local_alarm[1],
        **code,
    )
    await _test_local_no_service_call(
        hass,
        SERVICE_ALARM_ARM_HOME,
        "partial_arm",
        FIRST_LOCAL_ENTITY_ID,
        two_part_local_alarm[0],
        **code,
    )
    await _test_local_no_service_call(
        hass,
        SERVICE_ALARM_ARM_HOME,
        "partial_arm",
        SECOND_LOCAL_ENTITY_ID,
        two_part_local_alarm[1],
        **code,
    )
    await _test_local_no_service_call(
        hass,
        SERVICE_ALARM_ARM_NIGHT,
        "group_arm",
        FIRST_LOCAL_ENTITY_ID,
        two_part_local_alarm[0],
        **code,
    )
    await _test_local_no_service_call(
        hass,
        SERVICE_ALARM_ARM_NIGHT,
        "group_arm",
        SECOND_LOCAL_ENTITY_ID,
        two_part_local_alarm[1],
        **code,
    )
    with pytest.raises(HomeAssistantError):
        await _test_local_no_service_call(
            hass,
            SERVICE_ALARM_ARM_CUSTOM_BYPASS,
            "partial_arm",
            FIRST_LOCAL_ENTITY_ID,
            two_part_local_alarm[0],
            **code,
        )
    with pytest.raises(HomeAssistantError):
        await _test_local_no_service_call(
            hass,
            SERVICE_ALARM_ARM_CUSTOM_BYPASS,
            "partial_arm",
            SECOND_LOCAL_ENTITY_ID,
            two_part_local_alarm[1],
            **code,
        )
