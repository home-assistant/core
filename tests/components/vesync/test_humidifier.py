"""Tests for VeSync humidifiers."""

from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from homeassistant.components.humidifier import (
    ATTR_AVAILABLE_MODES,
    ATTR_HUMIDITY,
    ATTR_MAX_HUMIDITY,
    ATTR_MIN_HUMIDITY,
    DOMAIN as HUMIDIFIER_DOMAIN,
    MODE_AUTO,
    MODE_NORMAL,
    MODE_SLEEP,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_MODE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    HumidifierDeviceClass,
    HumidifierEntityFeature,
)
from homeassistant.components.vesync.const import VS_DISCOVERY, VS_HUMIDIFIERS
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_ENTITY_PICTURE,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_MODE,
    ATTR_SUPPORTED_FEATURES,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

TEST_HUMIDIFIER_ENTITIY = "humidifier.humidifier_300s"


async def test_discovered_unsupported_humidifier(
    hass: HomeAssistant, setup_platform, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the discovery mechanism can handle unsupported humidifiers."""
    mock_humidifier = MagicMock()
    mock_humidifier.device_type = "invalid_type"
    mock_humidifier.device_name = "invalid_name"
    config_dict = {"module": "invalid_module"}
    mock_config_dict = MagicMock()
    mock_config_dict.__getitem__.side_effect = config_dict.__getitem__
    mock_humidifier.config_dict = mock_config_dict

    async_dispatcher_send(hass, VS_DISCOVERY.format(VS_HUMIDIFIERS), [mock_humidifier])
    assert caplog.records[0].msg == "%s - Unknown device type/module - %s/%s"
    assert (
        caplog.messages[0]
        == "invalid_name - Unknown device type/module - invalid_type/invalid_module"
    )


async def test_attributes_humidifier(hass: HomeAssistant, setup_platform) -> None:
    """Test the humidifier attributes are correct."""
    state = hass.states.get(TEST_HUMIDIFIER_ENTITIY)
    assert state
    # From EntityDescription
    assert state.attributes.get(ATTR_DEVICE_CLASS) == HumidifierDeviceClass.HUMIDIFIER
    assert state.attributes.get(ATTR_ICON) == "mdi:air-humidifier"
    # Entity
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "Humidifier 300s"
    assert (
        state.attributes.get(ATTR_ENTITY_PICTURE)
        == "https://image.vesync.com/defaultImages/LV_600S_Series/icon_lv600s_humidifier_160.png"
    )
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_MIN_HUMIDITY) == 30
    assert state.attributes.get(ATTR_MAX_HUMIDITY) == 80
    assert state.attributes.get(ATTR_HUMIDITY) == 40
    assert state.attributes.get(ATTR_MODE) == MODE_NORMAL
    assert state.attributes.get(ATTR_AVAILABLE_MODES) == [
        MODE_AUTO,
        MODE_SLEEP,
        MODE_NORMAL,
    ]
    assert (
        state.attributes.get(ATTR_SUPPORTED_FEATURES) == HumidifierEntityFeature.MODES
    )
    assert state.attributes.get("warm_mist_feature") is False

    state = hass.states.get("light.humidifier_300s_night_light")
    assert state
    state = hass.states.get("number.humidifier_300s_mist_level")
    assert state
    state = hass.states.get("sensor.humidifier_300s_empty_water_tank")
    assert state
    state = hass.states.get("sensor.humidifier_300s_humidity")
    assert state
    state = hass.states.get("sensor.humidifier_300s_humidity_high")
    assert state
    state = hass.states.get("sensor.humidifier_300s_water_tank_lifted")
    assert state
    state = hass.states.get("switch.humidifier_300s_display")
    assert state
    state = hass.states.get("switch.humidifier_300s_automatic_stop")
    assert state


async def test_turn_on(hass: HomeAssistant, setup_platform) -> None:
    """Test the humidifier can be turned on."""
    with patch("pyvesync.vesyncfan.VeSyncHumid200300S.turn_on") as mock_turn_on:
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY},
            blocking=True,
        )
        await hass.async_block_till_done()

        mock_turn_on.assert_called_once()


async def test_turn_off(hass: HomeAssistant, setup_platform) -> None:
    """Test the humidifier can be turned off."""
    with patch("pyvesync.vesyncfan.VeSyncHumid200300S.turn_off") as mock_turn_off:
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY},
            blocking=True,
        )
        await hass.async_block_till_done()

        mock_turn_off.assert_called_once()


async def test_get_mode(hass: HomeAssistant, setup_platform) -> None:
    """Test the humidifier can change modes."""
    with patch(
        "pyvesync.vesyncfan.VeSyncHumid200300S.set_humidity_mode"
    ) as mock_set_mode:
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_SET_MODE,
            {ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY, ATTR_MODE: MODE_AUTO},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_mode.assert_called_with(MODE_AUTO)


async def test_set_mode(hass: HomeAssistant, setup_platform) -> None:
    """Test the humidifier can change modes."""
    with patch(
        "pyvesync.vesyncfan.VeSyncHumid200300S.set_humidity_mode"
    ) as mock_set_mode:
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_SET_MODE,
            {ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY, ATTR_MODE: MODE_AUTO},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_mode.assert_called_with(MODE_AUTO)

        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_SET_MODE,
            {ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY, ATTR_MODE: MODE_NORMAL},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_mode.assert_called_with("manual")

        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_SET_MODE,
            {ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY, ATTR_MODE: MODE_SLEEP},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_mode.assert_called_with(MODE_SLEEP)

        with pytest.raises(ValueError):
            await hass.services.async_call(
                HUMIDIFIER_DOMAIN,
                SERVICE_SET_MODE,
                {
                    ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY,
                    ATTR_MODE: "ModeThatDoesntExist",
                },
                blocking=True,
            )


async def test_set_mode_when_off(hass: HomeAssistant, setup_platform) -> None:
    """Test the humidifer can set the mode when off."""
    with patch(
        "pyvesync.vesyncfan.VeSyncHumid200300S.set_humidity_mode"
    ) as mock_set_mode, patch(
        "pyvesync.vesyncfan.VeSyncHumid200300S.is_on", new_callable=PropertyMock
    ) as mock_is_on, patch(
        "pyvesync.vesyncfan.VeSyncHumid200300S.turn_on"
    ) as mock_turn_on:
        mock_is_on.return_value = False

        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_SET_MODE,
            {ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY, ATTR_MODE: MODE_AUTO},
            blocking=True,
        )
        await hass.async_block_till_done()

        mock_set_mode.assert_called_with(MODE_AUTO)
        mock_is_on.assert_called()
        mock_turn_on.assert_called()


async def test_set_mode__no_available_modes(
    hass: HomeAssistant, setup_platform
) -> None:
    """Test the humidifer can set the mode when off."""
    with patch(
        "homeassistant.components.vesync.humidifier.VeSyncHumidifierHA.available_modes",
        new_callable=PropertyMock,
    ) as mock_available_modes:
        mock_available_modes.return_value = None

        with pytest.raises(ValueError) as ex_info:
            await hass.services.async_call(
                HUMIDIFIER_DOMAIN,
                SERVICE_SET_MODE,
                {
                    ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY,
                    ATTR_MODE: "ModeThatDoesntExist",
                },
                blocking=True,
            )

        assert ex_info.value.args[0] == "No available modes were specified"


async def test_set_humidity(hass: HomeAssistant, setup_platform) -> None:
    """Test the humidifier can set humidity level."""
    with patch(
        "pyvesync.vesyncfan.VeSyncHumid200300S.set_humidity"
    ) as mock_set_humidity:
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_SET_HUMIDITY,
            {ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY, ATTR_HUMIDITY: 60},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_humidity.assert_called_once_with(60)


async def test_set_humidity_when_off(hass: HomeAssistant, setup_platform) -> None:
    """Test the humidifier will turn on before it sets the humidity."""

    with patch(
        "pyvesync.vesyncfan.VeSyncHumid200300S.set_humidity"
    ) as mock_set_humidity, patch(
        "pyvesync.vesyncfan.VeSyncHumid200300S.is_on", new_callable=PropertyMock
    ) as mock_is_on, patch(
        "pyvesync.vesyncfan.VeSyncHumid200300S.turn_on"
    ) as mock_turn_on:
        mock_is_on.return_value = False

        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_SET_HUMIDITY,
            {ATTR_ENTITY_ID: TEST_HUMIDIFIER_ENTITIY, ATTR_HUMIDITY: 60},
            blocking=True,
        )
        await hass.async_block_till_done()

        mock_is_on.assert_called()
        mock_turn_on.assert_called()
        mock_set_humidity.assert_called_once_with(60)
