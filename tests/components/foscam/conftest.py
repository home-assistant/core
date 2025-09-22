"""Common stuff for Foscam tests."""

from libpyfoscamcgi.foscamcgi import (
    ERROR_FOSCAM_AUTH,
    ERROR_FOSCAM_CMD,
    ERROR_FOSCAM_UNAVAILABLE,
    ERROR_FOSCAM_UNKNOWN,
)

from homeassistant.components.foscam import config_flow

from .const import (
    CAMERA_MAC,
    CAMERA_NAME,
    INVALID_RESPONSE_CONFIG,
    OPERATOR_CONFIG,
    VALID_CONFIG,
)


def setup_mock_foscam_camera(mock_foscam_camera):
    """Mock FoscamCamera simulating behaviour using a base valid config."""

    def configure_mock_on_init(host, port, user, passwd, verbose=False):
        product_all_info_rc = 0
        dev_info_rc = 0
        dev_info_data = {}

        if (
            host != VALID_CONFIG[config_flow.CONF_HOST]
            or port != VALID_CONFIG[config_flow.CONF_PORT]
        ):
            product_all_info_rc = dev_info_rc = ERROR_FOSCAM_UNAVAILABLE

        elif (
            user
            not in [
                VALID_CONFIG[config_flow.CONF_USERNAME],
                OPERATOR_CONFIG[config_flow.CONF_USERNAME],
                INVALID_RESPONSE_CONFIG[config_flow.CONF_USERNAME],
            ]
            or passwd != VALID_CONFIG[config_flow.CONF_PASSWORD]
        ):
            product_all_info_rc = dev_info_rc = ERROR_FOSCAM_AUTH

        elif user == INVALID_RESPONSE_CONFIG[config_flow.CONF_USERNAME]:
            product_all_info_rc = dev_info_rc = ERROR_FOSCAM_UNKNOWN

        elif user == OPERATOR_CONFIG[config_flow.CONF_USERNAME]:
            dev_info_rc = ERROR_FOSCAM_CMD

        else:
            dev_info_data["devName"] = CAMERA_NAME
            dev_info_data["mac"] = CAMERA_MAC
            dev_info_data["productName"] = "Foscam Product"
            dev_info_data["firmwareVer"] = "1.2.3"
            dev_info_data["hardwareVer"] = "4.5.6"

        mock_foscam_camera.get_product_all_info.return_value = (product_all_info_rc, {})
        mock_foscam_camera.get_dev_info.return_value = (dev_info_rc, dev_info_data)
        mock_foscam_camera.get_port_info.return_value = (dev_info_rc, {})
        mock_foscam_camera.is_asleep.return_value = (0, True)
        mock_foscam_camera.get_infra_led_config.return_value = (0, {"mode": "1"})
        mock_foscam_camera.get_mirror_and_flip_setting.return_value = (
            0,
            {"isFlip": "0", "isMirror": "0"},
        )
        mock_foscam_camera.is_asleep.return_value = (0, "0")
        mock_foscam_camera.getWhiteLightBrightness.return_value = (0, {"enable": "1"})
        mock_foscam_camera.getSirenConfig.return_value = (0, {"sirenEnable": "1"})
        mock_foscam_camera.getAudioVolume.return_value = (0, {"volume": "100"})
        mock_foscam_camera.getSpeakVolume.return_value = (0, {"SpeakVolume": "100"})
        mock_foscam_camera.getVoiceEnableState.return_value = (0, {"isEnable": "1"})
        mock_foscam_camera.getLedEnableState.return_value = (0, {"isEnable": "0"})
        mock_foscam_camera.getWdrMode.return_value = (0, {"mode": "0"})
        mock_foscam_camera.getHdrMode.return_value = (0, {"mode": "0"})
        mock_foscam_camera.get_motion_detect_config.return_value = (0, 1)
        mock_foscam_camera.getSWCapabilities.return_value = (
            0,
            {
                "swCapabilities1": "100",
                "swCapabilities2": "100",
                "swCapabilities3": "100",
                "swCapabilities4": "100",
            },
        )
        mock_foscam_camera.get_motion_detect_config.return_value = (
            0,
            {"petEnable": "1", "carEnable": "1", "humanEnable": "1"},
        )
        return mock_foscam_camera

    mock_foscam_camera.side_effect = configure_mock_on_init
