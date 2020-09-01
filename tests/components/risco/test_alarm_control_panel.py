"""Tests for the Risco alarm control panel device."""
import pytest

from homeassistant.components.alarm_control_panel import DOMAIN as ALARM_DOMAIN
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_CUSTOM_BYPASS,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
)
from homeassistant.components.risco import CannotConnectError, UnauthorizedError
from homeassistant.components.risco.const import DOMAIN
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PIN,
    CONF_USERNAME,
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
from homeassistant.helpers.entity_component import async_update_entity

from tests.async_mock import MagicMock, PropertyMock, patch
from tests.common import MockConfigEntry

TEST_CONFIG = {
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
    CONF_PIN: "1234",
}
TEST_SITE_UUID = "test-site-uuid"
TEST_SITE_NAME = "test-site-name"
FIRST_ENTITY_ID = "alarm_control_panel.risco_test_site_name_partition_0"
SECOND_ENTITY_ID = "alarm_control_panel.risco_test_site_name_partition_1"

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
    SUPPORT_ALARM_ARM_AWAY | SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_NIGHT
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
def two_part_alarm():
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
        "homeassistant.components.risco.RiscoAPI.get_state",
        return_value=alarm_mock,
    ):
        yield alarm_mock


async def _setup_risco(hass, options={}):
    config_entry = MockConfigEntry(domain=DOMAIN, data=TEST_CONFIG, options=options)
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.risco.RiscoAPI.login",
        return_value=True,
    ), patch(
        "homeassistant.components.risco.RiscoAPI.site_uuid",
        new_callable=PropertyMock(return_value=TEST_SITE_UUID),
    ), patch(
        "homeassistant.components.risco.RiscoAPI.site_name",
        new_callable=PropertyMock(return_value=TEST_SITE_NAME),
    ), patch(
        "homeassistant.components.risco.RiscoAPI.close"
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


async def test_cannot_connect(hass):
    """Test connection error."""

    with patch(
        "homeassistant.components.risco.RiscoAPI.login",
        side_effect=CannotConnectError,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=TEST_CONFIG)
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        registry = await hass.helpers.entity_registry.async_get_registry()
        assert not registry.async_is_registered(FIRST_ENTITY_ID)
        assert not registry.async_is_registered(SECOND_ENTITY_ID)


async def test_unauthorized(hass):
    """Test unauthorized error."""

    with patch(
        "homeassistant.components.risco.RiscoAPI.login",
        side_effect=UnauthorizedError,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=TEST_CONFIG)
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        registry = await hass.helpers.entity_registry.async_get_registry()
        assert not registry.async_is_registered(FIRST_ENTITY_ID)
        assert not registry.async_is_registered(SECOND_ENTITY_ID)


async def test_setup(hass, two_part_alarm):
    """Test entity setup."""
    registry = await hass.helpers.entity_registry.async_get_registry()

    assert not registry.async_is_registered(FIRST_ENTITY_ID)
    assert not registry.async_is_registered(SECOND_ENTITY_ID)

    await _setup_risco(hass)

    assert registry.async_is_registered(FIRST_ENTITY_ID)
    assert registry.async_is_registered(SECOND_ENTITY_ID)

    registry = await hass.helpers.device_registry.async_get_registry()
    device = registry.async_get_device({(DOMAIN, TEST_SITE_UUID + "_0")}, {})
    assert device is not None
    assert device.manufacturer == "Risco"

    device = registry.async_get_device({(DOMAIN, TEST_SITE_UUID + "_1")}, {})
    assert device is not None
    assert device.manufacturer == "Risco"


async def _check_state(hass, alarm, property, state, entity_id, partition_id):
    with patch.object(alarm.partitions[partition_id], property, return_value=True):
        await async_update_entity(hass, entity_id)
        await hass.async_block_till_done()

        assert hass.states.get(entity_id).state == state


async def test_states(hass, two_part_alarm):
    """Test the various alarm states."""
    await _setup_risco(hass, CUSTOM_MAPPING_OPTIONS)

    assert hass.states.get(FIRST_ENTITY_ID).state == STATE_UNKNOWN
    for partition_id, entity_id in {0: FIRST_ENTITY_ID, 1: SECOND_ENTITY_ID}.items():
        await _check_state(
            hass,
            two_part_alarm,
            "triggered",
            STATE_ALARM_TRIGGERED,
            entity_id,
            partition_id,
        )
        await _check_state(
            hass, two_part_alarm, "arming", STATE_ALARM_ARMING, entity_id, partition_id
        )
        await _check_state(
            hass,
            two_part_alarm,
            "armed",
            STATE_ALARM_ARMED_AWAY,
            entity_id,
            partition_id,
        )
        await _check_state(
            hass,
            two_part_alarm,
            "partially_armed",
            STATE_ALARM_ARMED_HOME,
            entity_id,
            partition_id,
        )
        await _check_state(
            hass,
            two_part_alarm,
            "disarmed",
            STATE_ALARM_DISARMED,
            entity_id,
            partition_id,
        )

        groups = {"A": False, "B": False, "C": True, "D": False}
        with patch.object(
            two_part_alarm.partitions[partition_id],
            "groups",
            new_callable=PropertyMock(return_value=groups),
        ):
            await _check_state(
                hass,
                two_part_alarm,
                "partially_armed",
                STATE_ALARM_ARMED_NIGHT,
                entity_id,
                partition_id,
            )


async def _test_service_call(
    hass, service, method, entity_id, partition_id, *args, **kwargs
):
    with patch(f"homeassistant.components.risco.RiscoAPI.{method}") as set_mock:
        await _call_alarm_service(hass, service, entity_id, **kwargs)
        set_mock.assert_awaited_once_with(partition_id, *args)


async def _test_no_service_call(
    hass, service, method, entity_id, partition_id, **kwargs
):
    with patch(f"homeassistant.components.risco.RiscoAPI.{method}") as set_mock:
        await _call_alarm_service(hass, service, entity_id, **kwargs)
        set_mock.assert_not_awaited()


async def _call_alarm_service(hass, service, entity_id, **kwargs):
    data = {"entity_id": entity_id, **kwargs}

    await hass.services.async_call(
        ALARM_DOMAIN, service, service_data=data, blocking=True
    )


async def test_sets_custom_mapping(hass, two_part_alarm):
    """Test settings the various modes when mapping some states."""
    await _setup_risco(hass, CUSTOM_MAPPING_OPTIONS)

    registry = await hass.helpers.entity_registry.async_get_registry()
    entity = registry.async_get(FIRST_ENTITY_ID)
    assert entity.supported_features == EXPECTED_FEATURES

    await _test_service_call(hass, SERVICE_ALARM_DISARM, "disarm", FIRST_ENTITY_ID, 0)
    await _test_service_call(hass, SERVICE_ALARM_DISARM, "disarm", SECOND_ENTITY_ID, 1)
    await _test_service_call(hass, SERVICE_ALARM_ARM_AWAY, "arm", FIRST_ENTITY_ID, 0)
    await _test_service_call(hass, SERVICE_ALARM_ARM_AWAY, "arm", SECOND_ENTITY_ID, 1)
    await _test_service_call(
        hass, SERVICE_ALARM_ARM_HOME, "partial_arm", FIRST_ENTITY_ID, 0
    )
    await _test_service_call(
        hass, SERVICE_ALARM_ARM_HOME, "partial_arm", SECOND_ENTITY_ID, 1
    )
    await _test_service_call(
        hass, SERVICE_ALARM_ARM_NIGHT, "group_arm", FIRST_ENTITY_ID, 0, "C"
    )
    await _test_service_call(
        hass, SERVICE_ALARM_ARM_NIGHT, "group_arm", SECOND_ENTITY_ID, 1, "C"
    )


async def test_sets_full_custom_mapping(hass, two_part_alarm):
    """Test settings the various modes when mapping all states."""
    await _setup_risco(hass, FULL_CUSTOM_MAPPING)

    registry = await hass.helpers.entity_registry.async_get_registry()
    entity = registry.async_get(FIRST_ENTITY_ID)
    assert (
        entity.supported_features == EXPECTED_FEATURES | SUPPORT_ALARM_ARM_CUSTOM_BYPASS
    )

    await _test_service_call(hass, SERVICE_ALARM_DISARM, "disarm", FIRST_ENTITY_ID, 0)
    await _test_service_call(hass, SERVICE_ALARM_DISARM, "disarm", SECOND_ENTITY_ID, 1)
    await _test_service_call(hass, SERVICE_ALARM_ARM_AWAY, "arm", FIRST_ENTITY_ID, 0)
    await _test_service_call(hass, SERVICE_ALARM_ARM_AWAY, "arm", SECOND_ENTITY_ID, 1)
    await _test_service_call(
        hass, SERVICE_ALARM_ARM_HOME, "partial_arm", FIRST_ENTITY_ID, 0
    )
    await _test_service_call(
        hass, SERVICE_ALARM_ARM_HOME, "partial_arm", SECOND_ENTITY_ID, 1
    )
    await _test_service_call(
        hass, SERVICE_ALARM_ARM_NIGHT, "group_arm", FIRST_ENTITY_ID, 0, "C"
    )
    await _test_service_call(
        hass, SERVICE_ALARM_ARM_NIGHT, "group_arm", SECOND_ENTITY_ID, 1, "C"
    )
    await _test_service_call(
        hass, SERVICE_ALARM_ARM_CUSTOM_BYPASS, "group_arm", FIRST_ENTITY_ID, 0, "D"
    )
    await _test_service_call(
        hass, SERVICE_ALARM_ARM_CUSTOM_BYPASS, "group_arm", SECOND_ENTITY_ID, 1, "D"
    )


async def test_sets_with_correct_code(hass, two_part_alarm):
    """Test settings the various modes when code is required."""
    await _setup_risco(hass, {**CUSTOM_MAPPING_OPTIONS, **CODES_REQUIRED_OPTIONS})

    code = {"code": 1234}
    await _test_service_call(
        hass, SERVICE_ALARM_DISARM, "disarm", FIRST_ENTITY_ID, 0, **code
    )
    await _test_service_call(
        hass, SERVICE_ALARM_DISARM, "disarm", SECOND_ENTITY_ID, 1, **code
    )
    await _test_service_call(
        hass, SERVICE_ALARM_ARM_AWAY, "arm", FIRST_ENTITY_ID, 0, **code
    )
    await _test_service_call(
        hass, SERVICE_ALARM_ARM_AWAY, "arm", SECOND_ENTITY_ID, 1, **code
    )
    await _test_service_call(
        hass, SERVICE_ALARM_ARM_HOME, "partial_arm", FIRST_ENTITY_ID, 0, **code
    )
    await _test_service_call(
        hass, SERVICE_ALARM_ARM_HOME, "partial_arm", SECOND_ENTITY_ID, 1, **code
    )
    await _test_service_call(
        hass, SERVICE_ALARM_ARM_NIGHT, "group_arm", FIRST_ENTITY_ID, 0, "C", **code
    )
    await _test_service_call(
        hass, SERVICE_ALARM_ARM_NIGHT, "group_arm", SECOND_ENTITY_ID, 1, "C", **code
    )
    await _test_no_service_call(
        hass, SERVICE_ALARM_ARM_CUSTOM_BYPASS, "partial_arm", FIRST_ENTITY_ID, 0, **code
    )
    await _test_no_service_call(
        hass,
        SERVICE_ALARM_ARM_CUSTOM_BYPASS,
        "partial_arm",
        SECOND_ENTITY_ID,
        1,
        **code,
    )


async def test_sets_with_incorrect_code(hass, two_part_alarm):
    """Test settings the various modes when code is required and incorrect."""
    await _setup_risco(hass, {**CUSTOM_MAPPING_OPTIONS, **CODES_REQUIRED_OPTIONS})

    code = {"code": 4321}
    await _test_no_service_call(
        hass, SERVICE_ALARM_DISARM, "disarm", FIRST_ENTITY_ID, 0, **code
    )
    await _test_no_service_call(
        hass, SERVICE_ALARM_DISARM, "disarm", SECOND_ENTITY_ID, 1, **code
    )
    await _test_no_service_call(
        hass, SERVICE_ALARM_ARM_AWAY, "arm", FIRST_ENTITY_ID, 0, **code
    )
    await _test_no_service_call(
        hass, SERVICE_ALARM_ARM_AWAY, "arm", SECOND_ENTITY_ID, 1, **code
    )
    await _test_no_service_call(
        hass, SERVICE_ALARM_ARM_HOME, "partial_arm", FIRST_ENTITY_ID, 0, **code
    )
    await _test_no_service_call(
        hass, SERVICE_ALARM_ARM_HOME, "partial_arm", SECOND_ENTITY_ID, 1, **code
    )
    await _test_no_service_call(
        hass, SERVICE_ALARM_ARM_NIGHT, "group_arm", FIRST_ENTITY_ID, 0, **code
    )
    await _test_no_service_call(
        hass, SERVICE_ALARM_ARM_NIGHT, "group_arm", SECOND_ENTITY_ID, 1, **code
    )
    await _test_no_service_call(
        hass, SERVICE_ALARM_ARM_CUSTOM_BYPASS, "partial_arm", FIRST_ENTITY_ID, 0, **code
    )
    await _test_no_service_call(
        hass,
        SERVICE_ALARM_ARM_CUSTOM_BYPASS,
        "partial_arm",
        SECOND_ENTITY_ID,
        1,
        **code,
    )
