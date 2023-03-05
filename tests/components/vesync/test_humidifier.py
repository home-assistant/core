"""Tests for VeSync humidifiers."""

from unittest.mock import patch

from homeassistant.components.humidifier import (
    HumidifierDeviceClass,
    HumidifierEntityFeature,
)
from homeassistant.components.vesync.humidifier import (
    MAX_HUMIDITY,
    MIN_HUMIDITY,
    VeSyncHumidifierEntityDescription,
    VeSyncHumidifierHA,
)
from homeassistant.core import HomeAssistant

TEST_CID1 = "humidifier_200s"
TEST_CID2 = "humidifier_600s"
TEST_HUMIDIFIER_ENTITIY = f"humidifier.{ TEST_CID1 }"


# async def test_discovered_unsupported_humidifier(
#     hass: HomeAssistant, setup_platform, caplog: pytest.LogCaptureFixture
# ) -> None:
#     """Test the discovery mechanism can handle unsupported humidifiers."""
#     mock_humidifier = MagicMock()
#     mock_humidifier.device_type = "invalid_type"
#     mock_humidifier.device_name = "invalid_name"
#     config_dict = {"module": "invalid_module"}
#     mock_config_dict = MagicMock()
#     mock_config_dict.__getitem__.side_effect = config_dict.__getitem__
#     mock_humidifier.config_dict = mock_config_dict

#     async_dispatcher_send(hass, VS_DISCOVERY.format(VS_HUMIDIFIERS), [mock_humidifier])
#     assert caplog.records[0].msg == "%s - Unknown device type/module - %s/%s"
#     assert (
#         caplog.messages[0]
#         == "invalid_name - Unknown device type/module - invalid_type/invalid_module"
#     )


async def test_humidifier_entity(hass: HomeAssistant, humidifier) -> None:
    """Test the humidifier entity constructor."""
    description = VeSyncHumidifierEntityDescription()
    entity = VeSyncHumidifierHA(humidifier, description)

    assert entity.available_modes == ["normal"]
    assert entity.device == humidifier
    assert entity.device_class == HumidifierDeviceClass.HUMIDIFIER
    assert entity.entity_category is None
    assert entity.entity_description == description
    assert entity.entity_picture == "device image"
    assert entity.has_entity_name is False
    assert entity.icon == "mdi:air-humidifier"
    assert entity.max_humidity == MAX_HUMIDITY
    assert entity.min_humidity == MIN_HUMIDITY
    assert entity.mode == "normal"
    assert entity.name == "device name"
    assert entity.supported_features == HumidifierEntityFeature.MODES
    assert entity.target_humidity == 50
    assert entity.unique_id == "cid1"


async def test_humidifier_entity__unique_info(humidifier) -> None:
    """Test the humidifier unique_info impl."""
    description = VeSyncHumidifierEntityDescription()
    entity = VeSyncHumidifierHA(humidifier, description)

    assert entity.unique_info == "uuid"


async def test_humidifier_entity__extra_state_attributes(humidifier) -> None:
    """Test the humidifier extra_state_attributes impl."""
    description = VeSyncHumidifierEntityDescription()
    entity = VeSyncHumidifierHA(humidifier, description)

    assert entity.extra_state_attributes == {"warm_mist_feature": True}


async def test_humidifier_entity__is_on(humidifier) -> None:
    """Test the humidifier is_on impl."""
    description = VeSyncHumidifierEntityDescription()
    entity = VeSyncHumidifierHA(humidifier, description)

    assert entity.is_on is True

    humidifier.is_on = False
    assert entity.is_on is False


async def test_humidifier_entity__turn_on(humidifier) -> None:
    """Test the humidifier is_on impl."""
    description = VeSyncHumidifierEntityDescription()
    entity = VeSyncHumidifierHA(humidifier, description)

    with patch.object(entity, "schedule_update_ha_state") as mock_schedule:
        entity.turn_on()
        mock_schedule.assert_called_once()

    assert humidifier.turn_on.call_count == 1


# async def test_turn_on(hass: HomeAssistant, setup_platform) -> None:
#     """Test the humidifier can be turned on."""
#     with patch("pyvesync.vesyncfan.VeSyncHumid200300S.turn_on") as mock_turn_on:
#         await hass.services.async_call(
#             HUMIDIFIER_DOMAIN,
#             SERVICE_TURN_ON,
#             {ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY},
#             blocking=True,
#         )
#         await hass.async_block_till_done()

#         mock_turn_on.assert_called_once()


# async def test_turn_off(hass: HomeAssistant, setup_platform) -> None:
#     """Test the humidifier can be turned off."""
#     with patch("pyvesync.vesyncfan.VeSyncHumid200300S.turn_off") as mock_turn_off:
#         await hass.services.async_call(
#             HUMIDIFIER_DOMAIN,
#             SERVICE_TURN_OFF,
#             {ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY},
#             blocking=True,
#         )
#         await hass.async_block_till_done()

#         mock_turn_off.assert_called_once()


# async def test_get_mode(hass: HomeAssistant, setup_platform) -> None:
#     """Test the humidifier can change modes."""
#     with patch(
#         "pyvesync.vesyncfan.VeSyncHumid200300S.set_humidity_mode"
#     ) as mock_set_mode:
#         await hass.services.async_call(
#             HUMIDIFIER_DOMAIN,
#             SERVICE_SET_MODE,
#             {ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY, ATTR_MODE: MODE_AUTO},
#             blocking=True,
#         )
#         await hass.async_block_till_done()
#         mock_set_mode.assert_called_with(MODE_AUTO)


# async def test_set_mode(hass: HomeAssistant, setup_platform) -> None:
#     """Test the humidifier can change modes."""
#     with patch(
#         "pyvesync.vesyncfan.VeSyncHumid200300S.set_humidity_mode"
#     ) as mock_set_mode:
#         await hass.services.async_call(
#             HUMIDIFIER_DOMAIN,
#             SERVICE_SET_MODE,
#             {ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY, ATTR_MODE: MODE_AUTO},
#             blocking=True,
#         )
#         await hass.async_block_till_done()
#         mock_set_mode.assert_called_with(MODE_AUTO)

#         await hass.services.async_call(
#             HUMIDIFIER_DOMAIN,
#             SERVICE_SET_MODE,
#             {ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY, ATTR_MODE: MODE_NORMAL},
#             blocking=True,
#         )
#         await hass.async_block_till_done()
#         mock_set_mode.assert_called_with("manual")

#         await hass.services.async_call(
#             HUMIDIFIER_DOMAIN,
#             SERVICE_SET_MODE,
#             {ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY, ATTR_MODE: MODE_SLEEP},
#             blocking=True,
#         )
#         await hass.async_block_till_done()
#         mock_set_mode.assert_called_with(MODE_SLEEP)

#         with pytest.raises(ValueError):
#             await hass.services.async_call(
#                 HUMIDIFIER_DOMAIN,
#                 SERVICE_SET_MODE,
#                 {
#                     ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY,
#                     ATTR_MODE: "ModeThatDoesntExist",
#                 },
#                 blocking=True,
#             )


# async def test_set_mode_when_off(hass: HomeAssistant, setup_platform) -> None:
#     """Test the humidifer can set the mode when off."""
#     with patch(
#         "pyvesync.vesyncfan.VeSyncHumid200300S.set_humidity_mode"
#     ) as mock_set_mode, patch(
#         "pyvesync.vesyncfan.VeSyncHumid200300S.is_on", new_callable=PropertyMock
#     ) as mock_is_on, patch(
#         "pyvesync.vesyncfan.VeSyncHumid200300S.turn_on"
#     ) as mock_turn_on:
#         mock_is_on.return_value = False

#         await hass.services.async_call(
#             HUMIDIFIER_DOMAIN,
#             SERVICE_SET_MODE,
#             {ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY, ATTR_MODE: MODE_AUTO},
#             blocking=True,
#         )
#         await hass.async_block_till_done()

#         mock_set_mode.assert_called_with(MODE_AUTO)
#         mock_is_on.assert_called()
#         mock_turn_on.assert_called()


# async def test_set_mode__no_available_modes(
#     hass: HomeAssistant, setup_platform
# ) -> None:
#     """Test the humidifer can set the mode when off."""
#     with patch(
#         "homeassistant.components.vesync.humidifier.VeSyncHumidifierHA.available_modes",
#         new_callable=PropertyMock,
#     ) as mock_available_modes:
#         mock_available_modes.return_value = None

#         with pytest.raises(ValueError) as ex_info:
#             await hass.services.async_call(
#                 HUMIDIFIER_DOMAIN,
#                 SERVICE_SET_MODE,
#                 {
#                     ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY,
#                     ATTR_MODE: "ModeThatDoesntExist",
#                 },
#                 blocking=True,
#             )

#         assert ex_info.value.args[0] == "No available modes were specified"


# async def test_set_humidity(hass: HomeAssistant, setup_platform) -> None:
#     """Test the humidifier can set humidity level."""
#     with patch(
#         "pyvesync.vesyncfan.VeSyncHumid200300S.set_humidity"
#     ) as mock_set_humidity:
#         await hass.services.async_call(
#             HUMIDIFIER_DOMAIN,
#             SERVICE_SET_HUMIDITY,
#             {ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY, ATTR_HUMIDITY: 60},
#             blocking=True,
#         )
#         await hass.async_block_till_done()
#         mock_set_humidity.assert_called_once_with(60)


# async def test_set_humidity_when_off(hass: HomeAssistant, setup_platform) -> None:
#     """Test the humidifier will turn on before it sets the humidity."""

#     with patch(
#         "pyvesync.vesyncfan.VeSyncHumid200300S.set_humidity"
#     ) as mock_set_humidity, patch(
#         "pyvesync.vesyncfan.VeSyncHumid200300S.is_on", new_callable=PropertyMock
#     ) as mock_is_on, patch(
#         "pyvesync.vesyncfan.VeSyncHumid200300S.turn_on"
#     ) as mock_turn_on:
#         mock_is_on.return_value = False

#         await hass.services.async_call(
#             HUMIDIFIER_DOMAIN,
#             SERVICE_SET_HUMIDITY,
#             {ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY, ATTR_HUMIDITY: 60},
#             blocking=True,
#         )
#         await hass.async_block_till_done()

#         mock_is_on.assert_called()
#         mock_turn_on.assert_called()
#         mock_set_humidity.assert_called_once_with(60)
