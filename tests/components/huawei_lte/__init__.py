"""Tests for the huawei_lte component."""

from unittest.mock import MagicMock

from huawei_lte_api.enums.cradle import ConnectionStatusEnum


def magic_client() -> MagicMock:
    """Mock huawei_lte.Client with all API methods."""
    information = MagicMock(
        return_value={
            "DeviceName": "Test Router",
            "SerialNumber": "test-serial-number",
            "Imei": "123456789012345",
            "Imsi": "123451234567890",
            "Iccid": "12345678901234567890",
            "Msisdn": None,
            "HardwareVersion": "1.0.0",
            "SoftwareVersion": "2.0.0",
            "WebUIVersion": "3.0.0",
            "MacAddress1": "22:22:33:44:55:66",
            "MacAddress2": None,
            "WanIPAddress": "23.215.0.138",
            "wan_dns_address": "8.8.8.8",
            "WanIPv6Address": "2600:1406:3a00:21::173e:2e66",
            "wan_ipv6_dns_address": "2001:4860:4860:0:0:0:0:8888",
            "ProductFamily": "LTE",
            "Classify": "cpe",
            "supportmode": "LTE|WCDMA|GSM",
            "workmode": "LTE",
            "submask": "255.255.255.255",
            "Mccmnc": "20499",
            "iniversion": "test-ini-version",
            "uptime": "4242424",
            "ImeiSvn": "01",
            "WifiMacAddrWl0": "22:22:33:44:55:77",
            "WifiMacAddrWl1": "22:22:33:44:55:88",
            "spreadname_en": "Huawei 4G Router N123",
            "spreadname_zh": "\u534e\u4e3a4G\u8def\u7531 N123",
        }
    )
    basic_information = MagicMock(
        return_value={
            "classify": "cpe",
            "devicename": "Test Router",
            "multimode": "0",
            "productfamily": "LTE",
            "restore_default_status": "0",
            "sim_save_pin_enable": "1",
            "spreadname_en": "Huawei 4G Router N123",
            "spreadname_zh": "\u534e\u4e3a4G\u8def\u7531 N123",
        }
    )
    signal = MagicMock(
        return_value={
            "pci": "123",
            "sc": None,
            "cell_id": "12345678",
            "rssi": "-70dBm",
            "rsrp": "-100dBm",
            "rsrq": "-10.0dB",
            "sinr": "10dB",
            "rscp": None,
            "ecio": None,
            "mode": "7",
            "ulbandwidth": "20MHz",
            "dlbandwidth": "20MHz",
            "txpower": "PPusch:-1dBm PPucch:-11dBm PSrs:10dBm PPrach:0dBm",
            "tdd": None,
            "ul_mcs": "mcsUpCarrier1:20",
            "dl_mcs": "mcsDownCarrier1Code0:8 mcsDownCarrier1Code1:9",
            "earfcn": "DL:123 UL:45678",
            "rrc_status": "1",
            "rac": None,
            "lac": None,
            "tac": "12345",
            "band": "1",
            "nei_cellid": "23456789",
            "plmn": "20499",
            "ims": "0",
            "wdlfreq": None,
            "lteulfreq": "19697",
            "ltedlfreq": "21597",
            "transmode": "TM[4]",
            "enodeb_id": "0012345",
            "cqi0": "11",
            "cqi1": "5",
            "ulfrequency": "1969700kHz",
            "dlfrequency": "2159700kHz",
            "arfcn": None,
            "bsic": None,
            "rxlev": None,
        }
    )

    check_notifications = MagicMock(
        return_value={
            "UnreadMessage": "2",
            "SmsStorageFull": "0",
            "OnlineUpdateStatus": "42",
            "SimOperEvent": "0",
        }
    )
    status = MagicMock(
        return_value={
            "ConnectionStatus": str(ConnectionStatusEnum.CONNECTED.value),
            "WifiConnectionStatus": None,
            "SignalStrength": None,
            "SignalIcon": "5",
            "CurrentNetworkType": "19",
            "CurrentServiceDomain": "3",
            "RoamingStatus": "0",
            "BatteryStatus": None,
            "BatteryLevel": None,
            "BatteryPercent": None,
            "simlockStatus": "0",
            "PrimaryDns": "8.8.8.8",
            "SecondaryDns": "8.8.4.4",
            "wififrequence": "1",
            "flymode": "0",
            "PrimaryIPv6Dns": "2001:4860:4860:0:0:0:0:8888",
            "SecondaryIPv6Dns": "2001:4860:4860:0:0:0:0:8844",
            "CurrentWifiUser": "42",
            "TotalWifiUser": "64",
            "currenttotalwifiuser": "0",
            "ServiceStatus": "2",
            "SimStatus": "1",
            "WifiStatus": "1",
            "CurrentNetworkTypeEx": "101",
            "maxsignal": "5",
            "wifiindooronly": "0",
            "cellroam": "1",
            "classify": "cpe",
            "usbup": "0",
            "wifiswitchstatus": "1",
            "WifiStatusExCustom": "0",
            "hvdcp_online": "0",
        }
    )
    month_statistics = MagicMock(
        return_value={
            "CurrentMonthDownload": "1000000000",
            "CurrentMonthUpload": "500000000",
            "MonthDuration": "720000",
            "MonthLastClearTime": "2025-07-01",
            "CurrentDayUsed": "123456789",
            "CurrentDayDuration": "10000",
        }
    )
    traffic_statistics = MagicMock(
        return_value={
            "CurrentConnectTime": "123456",
            "CurrentUpload": "2000000000",
            "CurrentDownload": "5000000000",
            "CurrentDownloadRate": "700",
            "CurrentUploadRate": "600",
            "TotalUpload": "20000000000",
            "TotalDownload": "50000000000",
            "TotalConnectTime": "1234567",
            "showtraffic": "1",
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
            "LocalDeleted": "0",
            "SimUnread": "0",
            "SimInbox": "0",
            "SimOutbox": "0",
            "SimDraft": "0",
            "LocalMax": "500",
            "SimMax": "30",
            "SimUsed": "0",
            "NewMsg": "0",
        }
    )

    mobile_dataswitch = MagicMock(return_value={"dataswitch": "1"})

    lan_host_info = MagicMock(
        return_value={
            "Hosts": {
                "Host": [
                    {
                        "Active": "0",
                        "ActualName": "TestDevice1",
                        "AddressSource": "DHCP",
                        "AssociatedSsid": None,
                        "AssociatedTime": None,
                        "HostName": "TestDevice1",
                        "ID": "InternetGatewayDevice.LANDevice.1.Hosts.Host.9.",
                        "InterfaceType": "Wireless",
                        "IpAddress": "192.168.1.100",
                        "LeaseTime": "2204542",
                        "MacAddress": "AA:BB:CC:DD:EE:FF",
                        "isLocalDevice": "0",
                    },
                    {
                        "Active": "1",
                        "ActualName": "TestDevice2",
                        "AddressSource": "DHCP",
                        "AssociatedSsid": "TestSSID",
                        "AssociatedTime": "258632",
                        "HostName": "TestDevice2",
                        "ID": "InternetGatewayDevice.LANDevice.1.Hosts.Host.17.",
                        "InterfaceType": "Wireless",
                        "IpAddress": "192.168.1.101",
                        "LeaseTime": "552115",
                        "MacAddress": "11:22:33:44:55:66",
                        "isLocalDevice": "0",
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
                        "ActualName": "TestDevice2",
                        "AssociatedSsid": "TestSSID",
                        "AssociatedTime": "258632",
                        "Frequency": "2.4GHz",
                        "HostName": "TestDevice2",
                        "ID": "InternetGatewayDevice.LANDevice.1.Hosts.Host.17.",
                        "IpAddress": "192.168.1.101;fe80::b222:33ff:fe44:5566",
                        "MacAddress": "11:22:33:44:55:66",
                    }
                ]
            }
        }
    )
    multi_basic_settings = MagicMock(
        return_value={"Ssid": [{"wifiisguestnetwork": "1", "WifiEnable": "0"}]}
    )
    wifi_feature_switch = MagicMock(
        return_value={
            "wifi_dbdc_enable": "0",
            "acmode_enable": "1",
            "wifiautocountry_enabled": "0",
            "wps_cancel_enable": "1",
            "wifimacfilterextendenable": "1",
            "wifimaxmacfilternum": "32",
            "paraimmediatework_enable": "1",
            "guestwifi_enable": "0",
            "wifi5gnamepostfix": "_5G",
            "wifiguesttimeextendenable": "1",
            "chinesessid_enable": "0",
            "isdoublechip": "1",
            "opennonewps_enable": "1",
            "wifi_country_enable": "0",
            "wifi5g_enabled": "1",
            "wifiwpsmode": "0",
            "pmf_enable": "1",
            "support_trigger_dualband_wps": "1",
            "maxapnum": "4",
            "wifi_chip_maxassoc": "32",
            "wifiwpssuportwepnone": "0",
            "maxassocoffloadon": None,
            "guidefrequencyenable": "0",
            "showssid_enable": "0",
            "wifishowradioswitch": "3",
            "wifispecialcharenable": "1",
            "wifi24g_switch_enable": "1",
            "wifi_dfs_enable": "0",
            "show_maxassoc": "0",
            "hilink_dbho_enable": "1",
            "oledshowpassword": "1",
            "doubleap5g_enable": "0",
            "wps_switch_enable": "1",
        }
    )

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
