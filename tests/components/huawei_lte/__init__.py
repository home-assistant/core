"""Tests for the huawei_lte component."""

from unittest.mock import MagicMock

from huawei_lte_api.enums.cradle import ConnectionStatusEnum


def magic_client(multi_basic_settings_value: dict) -> MagicMock:
    """Mock huawei_lte.Client."""
    information = MagicMock(return_value={"SerialNumber": "test-serial-number"})
    check_notifications = MagicMock(return_value={"SmsStorageFull": 0})
    status = MagicMock(
        return_value={"ConnectionStatus": ConnectionStatusEnum.CONNECTED.value}
    )
    multi_basic_settings = MagicMock(return_value=multi_basic_settings_value)
    wifi_feature_switch = MagicMock(return_value={"wifi24g_switch_enable": 1})
    device = MagicMock(information=information)
    monitoring = MagicMock(check_notifications=check_notifications, status=status)
    wlan = MagicMock(
        multi_basic_settings=multi_basic_settings,
        wifi_feature_switch=wifi_feature_switch,
    )
    return MagicMock(device=device, monitoring=monitoring, wlan=wlan)
