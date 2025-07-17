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


def magic_client_full() -> MagicMock:
    """Extended mock for huawei_lte.Client with all API methods."""
    information = MagicMock(
        return_value={
            "SerialNumber": "test-serial-number",
            "DeviceName": "Test Router",
            "HardwareVersion": "1.0.0",
            "SoftwareVersion": "2.0.0",
        }
    )
    basic_information = MagicMock(
        return_value={"devicename": "Test Router", "SoftwareVersion": "2.0.0"}
    )
    signal = MagicMock(
        return_value={"rssi": "-70", "rsrp": "-100", "rsrq": "-10", "sinr": "10"}
    )

    check_notifications = MagicMock(return_value={"SmsStorageFull": 0})
    status = MagicMock(return_value={"ConnectionStatus": "901"})
    month_statistics = MagicMock(
        return_value={
            "CurrentMonthDownload": "1000000000",
            "CurrentMonthUpload": "500000000",
            "MonthDuration": "720000",
        }
    )
    traffic_statistics = MagicMock(
        return_value={
            "CurrentDownload": "5000000000",
            "CurrentUpload": "2000000000",
            "TotalDownload": "50000000000",
            "TotalUpload": "20000000000",
        }
    )

    current_plmn = MagicMock(
        return_value={
            "State": "1",
            "FullName": "Test Network",
            "ShortName": "Test",
            "Numeric": "12345",
        }
    )
    net_mode = MagicMock(
        return_value={
            "NetworkMode": "03",
            "NetworkBand": "3FFFFFFF",
            "LTEBand": "7FFFFFFFFFFFFFFF",
        }
    )

    sms_count = MagicMock(
        return_value={
            "LocalUnread": "0",
            "LocalInbox": "5",
            "LocalOutbox": "2",
            "LocalDraft": "1",
            "SimUnread": "0",
            "SimInbox": "0",
            "SimOutbox": "0",
            "SimDraft": "0",
        }
    )

    mobile_dataswitch = MagicMock(return_value={"dataswitch": "1"})

    lan_host_info = MagicMock(
        return_value={
            "Hosts": {
                "Host": [
                    {
                        "ID": "1",
                        "MacAddress": "AA:BB:CC:DD:EE:FF",
                        "IpAddress": "192.168.1.100",
                        "HostName": "TestDevice1",
                        "AssociatedSsid": "TestSSID",
                    },
                    {
                        "ID": "2",
                        "MacAddress": "11:22:33:44:55:66",
                        "IpAddress": "192.168.1.101",
                        "HostName": "TestDevice2",
                        "AssociatedSsid": "TestSSID",
                    },
                ]
            }
        }
    )
    wlan_host_list = MagicMock(
        return_value={
            "Hosts": {
                "Host": [
                    {
                        "ID": "1",
                        "MacAddress": "AA:BB:CC:DD:EE:FF",
                        "IpAddress": "192.168.1.100",
                        "HostName": "TestDevice1",
                    }
                ]
            }
        }
    )
    multi_basic_settings = MagicMock(
        return_value={"Ssid": [{"wifiisguestnetwork": "1", "WifiEnable": "0"}]}
    )
    wifi_feature_switch = MagicMock(return_value={"wifi24g_switch_enable": 1})

    device = MagicMock(
        information=information, basic_information=basic_information, signal=signal
    )
    monitoring = MagicMock(
        check_notifications=check_notifications,
        status=status,
        month_statistics=month_statistics,
        traffic_statistics=traffic_statistics,
    )
    net = MagicMock(current_plmn=current_plmn, net_mode=net_mode)
    sms = MagicMock(sms_count=sms_count)
    dial_up = MagicMock(mobile_dataswitch=mobile_dataswitch)
    lan = MagicMock(host_info=lan_host_info)
    wlan = MagicMock(
        multi_basic_settings=multi_basic_settings,
        wifi_feature_switch=wifi_feature_switch,
        host_list=wlan_host_list,
    )

    return MagicMock(
        device=device,
        monitoring=monitoring,
        net=net,
        sms=sms,
        dial_up=dial_up,
        lan=lan,
        wlan=wlan,
    )
