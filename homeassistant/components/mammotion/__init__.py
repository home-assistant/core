"""The Mammotion Luba integration."""

from __future__ import annotations

from aiohttp import ClientConnectorError
from pymammotion import CloudIOTGateway
from pymammotion.aliyun.model.aep_response import AepResponse
from pymammotion.aliyun.model.connect_response import ConnectResponse
from pymammotion.aliyun.model.dev_by_account_response import ListingDevByAccountResponse
from pymammotion.aliyun.model.login_by_oauth_response import LoginByOAuthResponse
from pymammotion.aliyun.model.regions_response import RegionResponse
from pymammotion.aliyun.model.session_by_authcode_response import (
    SessionByAuthCodeResponse,
)
from pymammotion.data.model.account import Credentials
from pymammotion.http.http import MammotionHTTP
from pymammotion.http.model.http import LoginResponseData, Response
from pymammotion.mammotion.devices.mammotion import ConnectionPreference, Mammotion
from pymammotion.utility.device_config import DeviceConfig

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    CONF_ACCOUNTNAME,
    CONF_AEP_DATA,
    CONF_AUTH_DATA,
    CONF_CONNECT_DATA,
    CONF_DEVICE_DATA,
    CONF_DEVICE_NAME,
    CONF_MAMMOTION_DATA,
    CONF_REGION_DATA,
    CONF_RETRY_COUNT,
    CONF_SESSION_DATA,
    CONF_STAY_CONNECTED_BLUETOOTH,
    CONF_USE_WIFI,
    DEFAULT_RETRY_COUNT,
    DEVICE_SUPPORT,
    DOMAIN,
    EXPIRED_CREDENTIAL_EXCEPTIONS,
    LOGGER,
)
from .coordinator import (
    MammotionBaseUpdateCoordinator,
    MammotionDeviceVersionUpdateCoordinator,
    MammotionMaintenanceUpdateCoordinator,
    MammotionMapUpdateCoordinator,
    MammotionReportUpdateCoordinator,
)
from .models import MammotionDevices, MammotionMowerData

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.LAWN_MOWER,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
]

type MammotionConfigEntry = ConfigEntry[list[MammotionMowerData]]


async def async_setup_entry(hass: HomeAssistant, entry: MammotionConfigEntry) -> bool:
    """Set up Mammotion Luba from a config entry."""

    if not entry.options:
        hass.config_entries.async_update_entry(
            entry,
            options={CONF_STAY_CONNECTED_BLUETOOTH: False},
        )

    device_name = entry.data.get(CONF_DEVICE_NAME)
    address = entry.data.get(CONF_ADDRESS)
    mammotion = Mammotion()
    account = entry.data.get(CONF_ACCOUNTNAME)
    password = entry.data.get(CONF_PASSWORD)

    stay_connected_ble = entry.data.get(CONF_STAY_CONNECTED_BLUETOOTH, False)
    use_wifi = entry.data.get(CONF_USE_WIFI, True)

    mammotion_devices: list[MammotionMowerData] = []

    if account and password:
        credentials = Credentials()
        credentials.email = account
        credentials.password = password
        try:
            cloud_client = await check_and_restore_cloud(hass, entry)
            if cloud_client is None:
                await mammotion.login_and_initiate_cloud(account, password)
            else:
                await mammotion.initiate_cloud_connection(account, cloud_client)
        except ClientConnectorError as err:
            raise ConfigEntryNotReady(err)
        except EXPIRED_CREDENTIAL_EXCEPTIONS as exc:
            LOGGER.debug(exc)
            await mammotion.login_and_initiate_cloud(account, password, True)



        if mqtt_client := mammotion.mqtt_list.get(account):
            store_cloud_credentials(hass, entry, mqtt_client.cloud_client)
            for (
                device
            ) in mqtt_client.cloud_client.devices_by_account_response.data.data:
                if not device.deviceName.startswith(DEVICE_SUPPORT):
                    continue
                maintenance_coordinator = MammotionMaintenanceUpdateCoordinator(
                    hass, entry, device, mammotion
                )
                version_coordinator = MammotionDeviceVersionUpdateCoordinator(
                    hass, entry, device, mammotion
                )
                report_coordinator = MammotionReportUpdateCoordinator(
                    hass, entry, device, mammotion
                )
                map_coordinator = MammotionMapUpdateCoordinator(
                    hass, entry, device, mammotion
                )
                # other coordinator
                await maintenance_coordinator.async_config_entry_first_refresh()
                await version_coordinator.async_config_entry_first_refresh()
                await report_coordinator.async_config_entry_first_refresh()
                await map_coordinator.async_config_entry_first_refresh()

                device_config = DeviceConfig()
                if (
                    device_limits := device_config.get_working_parameters(
                        device.productKey
                    )
                    is None
                ):
                    if version_coordinator.data.model_id == "":
                        device_limits = device_config.get_best_default(
                            device.productKey
                        )
                    else:
                        device_limits = device_config.get_working_parameters(
                            version_coordinator.data.model_id
                        )

                mammotion_device = mammotion.get_device_by_name(device.deviceName)
                if address:
                    ble_device = bluetooth.async_ble_device_from_address(hass, address)
                    if ble_device:
                        mammotion_device.add_ble(ble_device)
                        mammotion_device.ble().set_disconnect_strategy(
                            not stay_connected_ble
                        )
                if not use_wifi:
                    mammotion_device.preference = ConnectionPreference.BLUETOOTH
                    await mammotion_device.cloud().stop()
                    mammotion_device.cloud().mqtt.disconnect() if mammotion_device.cloud().mqtt.is_connected() else None

                mammotion_devices.append(
                    MammotionMowerData(
                        name=device.deviceName,
                        device=device,
                        device_limits=device_limits,
                        api=mammotion,
                        maintenance_coordinator=maintenance_coordinator,
                        reporting_coordinator=report_coordinator,
                        version_coordinator=version_coordinator,
                        map_coordinator=map_coordinator,
                    )
                )

    entry.runtime_data = mammotion_devices
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def store_cloud_credentials(hass, config_entry, cloud_client: CloudIOTGateway) -> None:
    """Store cloud credentials in config entry."""

    if cloud_client is not None:
        config_updates = {
            **config_entry.data,
            CONF_CONNECT_DATA: cloud_client.connect_response,
            CONF_AUTH_DATA: cloud_client.login_by_oauth_response,
            CONF_REGION_DATA: cloud_client.region_response,
            CONF_AEP_DATA: cloud_client.aep_response,
            CONF_SESSION_DATA: cloud_client.session_by_authcode_response,
            CONF_DEVICE_DATA: cloud_client.devices_by_account_response,
            CONF_MAMMOTION_DATA: cloud_client.mammotion_http.response,
        }
        hass.config_entries.async_update_entry(config_entry, data=config_updates)


async def check_and_restore_cloud(
    hass: HomeAssistant, entry: MammotionConfigEntry
) -> CloudIOTGateway | None:
    """Check and restore previous cloud connection."""

    auth_data = entry.data.get(CONF_AUTH_DATA)
    region_data = entry.data.get(CONF_REGION_DATA)
    aep_data = entry.data.get(CONF_AEP_DATA)
    session_data = entry.data.get(CONF_SESSION_DATA)
    device_data = entry.data.get(CONF_DEVICE_DATA)
    connect_data = entry.data.get(CONF_CONNECT_DATA)
    mammotion_data = entry.data.get(CONF_MAMMOTION_DATA)

    if any(
        data is None
        for data in [
            auth_data,
            region_data,
            aep_data,
            session_data,
            device_data,
            connect_data,
            mammotion_data,
        ]
    ):
        return None

    cloud_client = CloudIOTGateway(
        connect_response=ConnectResponse.from_dict(connect_data)
        if isinstance(connect_data, dict)
        else connect_data,
        aep_response=AepResponse.from_dict(aep_data)
        if isinstance(aep_data, dict)
        else aep_data,
        region_response=RegionResponse.from_dict(region_data)
        if isinstance(region_data, dict)
        else region_data,
        session_by_authcode_response=SessionByAuthCodeResponse.from_dict(session_data)
        if isinstance(session_data, dict)
        else session_data,
        dev_by_account=ListingDevByAccountResponse.from_dict(device_data)
        if isinstance(device_data, dict)
        else device_data,
        login_by_oauth_response=LoginByOAuthResponse.from_dict(auth_data)
        if isinstance(auth_data, dict)
        else auth_data,
    )

    if isinstance(mammotion_data, dict):
        mammotion_data = Response[LoginResponseData].from_dict(mammotion_data)
        mammotion_http = MammotionHTTP()
        mammotion_http.response = mammotion_data
        mammotion_http.login_info = mammotion_data.data
        cloud_client.set_http(mammotion_http)

    await hass.async_add_executor_job(cloud_client.check_or_refresh_session)
    print("restore cloud")
    return cloud_client


async def _async_update_listener(
    hass: HomeAssistant, entry: MammotionConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: MammotionConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        for mower in entry.runtime_data:
            await mower.api.remove_device(mower.name)
    return unload_ok
