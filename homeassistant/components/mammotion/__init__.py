"""The Mammotion Luba integration."""

from __future__ import annotations

import contextlib

from aiohttp import ClientConnectorError
from pymammotion import CloudIOTGateway
from pymammotion.aliyun.model.aep_response import AepResponse
from pymammotion.aliyun.model.connect_response import ConnectResponse
from pymammotion.aliyun.model.dev_by_account_response import (
    Device,
    ListingDevAccountResponse,
)
from pymammotion.aliyun.model.login_by_oauth_response import LoginByOAuthResponse
from pymammotion.aliyun.model.regions_response import RegionResponse
from pymammotion.aliyun.model.session_by_authcode_response import (
    SessionByAuthCodeResponse,
)
from pymammotion.data.model.account import Credentials
from pymammotion.homeassistant import HomeAssistantMowerApi
from pymammotion.http.http import MammotionHTTP
from pymammotion.http.model.http import LoginResponseData, Response
from pymammotion.http.model.response_factory import response_factory
from pymammotion.mammotion.devices.mammotion import ConnectionPreference, Mammotion
from Tea.exceptions import UnretryableException

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry

from .config import MammotionConfigStore
from .const import (
    CONF_ACCOUNTNAME,
    CONF_AEP_DATA,
    CONF_AUTH_DATA,
    CONF_BLE_DEVICES,
    CONF_CONNECT_DATA,
    CONF_DEVICE_DATA,
    CONF_MAMMOTION_DATA,
    CONF_REGION_DATA,
    CONF_SESSION_DATA,
    CONF_STAY_CONNECTED_BLUETOOTH,
    CONF_USE_WIFI,
    DEVICE_SUPPORT,
    DOMAIN,
    EXPIRED_CREDENTIAL_EXCEPTIONS,
)
from .coordinator import MammotionMowerUpdateCoordinator
from .models import MammotionDevices, MammotionMowerData

PLATFORMS: list[Platform] = [Platform.LAWN_MOWER]

type MammotionConfigEntry = ConfigEntry[MammotionDevices]


async def async_setup_entry(hass: HomeAssistant, entry: MammotionConfigEntry) -> bool:
    """Set up Mammotion Luba from a config entry."""

    addresses = entry.data.get(CONF_BLE_DEVICES, {})
    mammotion = Mammotion()
    account = entry.data.get(CONF_ACCOUNTNAME)
    password = entry.data.get(CONF_PASSWORD)

    stay_connected_ble = entry.data.get(CONF_STAY_CONNECTED_BLUETOOTH, False)

    hass.config_entries.async_update_entry(
        entry,
        options={CONF_STAY_CONNECTED_BLUETOOTH: stay_connected_ble},
    )

    stay_connected_ble = entry.options.get(CONF_STAY_CONNECTED_BLUETOOTH, False)

    use_wifi = entry.data.get(CONF_USE_WIFI, True)

    mammotion_mowers: list[MammotionMowerData] = []
    mammotion_devices: MammotionDevices = MammotionDevices([])

    cloud_client: CloudIOTGateway | None = None
    if account and password:
        credentials = Credentials()
        credentials.email = account
        credentials.password = password
        try:
            with contextlib.suppress(KeyError):
                cloud_client = await check_and_restore_cloud(hass, entry)
            if cloud_client is None:
                await mammotion.login_and_initiate_cloud(account, password)
            else:
                if cloud_client.mammotion_http.login_info is None:
                    mammotion_http = MammotionHTTP()
                    await mammotion_http.login(account, password)
                    cloud_client.set_http(mammotion_http)
                await mammotion.initiate_cloud_connection(account, cloud_client)
        except ClientConnectorError as err:
            raise ConfigEntryNotReady(err) from err
        except EXPIRED_CREDENTIAL_EXCEPTIONS:
            await mammotion.login_and_initiate_cloud(account, password, True)
        except UnretryableException as err:
            raise ConfigEntryError(err) from err

        aliyun_mqtt_client = mammotion.mqtt_list.get(f"{account}_aliyun")
        mammotion_mqtt_client = mammotion.mqtt_list.get(f"{account}_mammotion")

        if aliyun_mqtt_client:
            mqtt_client = aliyun_mqtt_client
            store_cloud_credentials(hass, entry, mqtt_client.cloud_client)
        elif mammotion_mqtt_client:
            mqtt_client = mammotion_mqtt_client
            store_cloud_credentials(hass, entry, mqtt_client.cloud_client)

        device_list: list[Device] = []
        shimed_cloud_devices = []
        cloud_devices = []

        if mammotion_mqtt_client:
            shimed_cloud_devices = mammotion.shim_cloud_devices(
                mammotion_mqtt_client.cloud_client.mammotion_http.device_records.records
            )
            device_list.extend(shimed_cloud_devices)
        if aliyun_mqtt_client:
            cloud_devices = (
                aliyun_mqtt_client.cloud_client.devices_by_account_response.data.data
            )
            device_list.extend(cloud_devices)

        for device in device_list:
            if not device.device_name.startswith(DEVICE_SUPPORT):
                continue

            if device in shimed_cloud_devices:
                mammotion_device = mammotion.get_or_create_device_by_name(
                    device, mammotion_mqtt_client, None
                )
            elif device in cloud_devices:
                mammotion_device = mammotion.get_or_create_device_by_name(
                    device, aliyun_mqtt_client, None
                )
            else:
                mammotion_device = mammotion.get_or_create_device_by_name(
                    device, None, None
                )

            if device_ble_address := addresses.get(device.device_name, None):
                mammotion_device.state.mower_state.ble_mac = device_ble_address
                ble_device = bluetooth.async_ble_device_from_address(
                    hass, device_ble_address.upper(), True
                )
                if ble_device:
                    ble = mammotion_device.add_ble(ble_device)
                    ble.set_disconnect_strategy(disconnect=not stay_connected_ble)

            api = HomeAssistantMowerApi(async_get_clientsession(hass))

            coordinator = MammotionMowerUpdateCoordinator(hass, entry, device, api)

            await coordinator.async_restore_data()

            if not use_wifi:
                mammotion_device.preference = ConnectionPreference.BLUETOOTH
                if cloud := mammotion_device.cloud:
                    cloud.stop()
                    cloud.mqtt.disconnect() if cloud.mqtt.is_connected() else None
                    mammotion_device.remove_cloud()

            mammotion_mowers.append(
                MammotionMowerData(
                    name=device.device_name,
                    api=api,
                    coordinator=coordinator,
                    device=device,
                )
            )

    mammotion_devices.mowers = mammotion_mowers
    entry.runtime_data = mammotion_devices

    async def shutdown_mammotion(_: Event | None = None) -> None:
        await api.mammotion.stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown_mammotion)
    )
    entry.async_on_unload(shutdown_mammotion)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def store_cloud_credentials(
    hass: HomeAssistant,
    config_entry: MammotionConfigEntry,
    cloud_client: CloudIOTGateway,
) -> None:
    """Store cloud credentials in config entry."""

    if cloud_client is not None:
        mammotion_data = config_entry.data.get(CONF_MAMMOTION_DATA)
        if cloud_client.mammotion_http is not None:
            mammotion_data = cloud_client.mammotion_http.response

        config_updates = {
            **config_entry.data,
            CONF_CONNECT_DATA: cloud_client.connect_response,
            CONF_AUTH_DATA: cloud_client.login_by_oauth_response,
            CONF_REGION_DATA: cloud_client.region_response,
            CONF_AEP_DATA: cloud_client.aep_response,
            CONF_SESSION_DATA: cloud_client.session_by_authcode_response,
            CONF_DEVICE_DATA: cloud_client.devices_by_account_response,
            CONF_MAMMOTION_DATA: mammotion_data,
        }
        hass.config_entries.async_update_entry(config_entry, data=config_updates)


async def check_and_restore_cloud(
    hass: HomeAssistant, entry: MammotionConfigEntry
) -> CloudIOTGateway | None:
    """Check and restore previous cloud connection."""

    auth_data = entry.data[CONF_AUTH_DATA]
    region_data = entry.data[CONF_REGION_DATA]
    aep_data = entry.data[CONF_AEP_DATA]
    session_data = entry.data[CONF_SESSION_DATA]
    device_data = entry.data[CONF_DEVICE_DATA]
    connect_data = entry.data[CONF_CONNECT_DATA]
    mammotion_data = entry.data[CONF_MAMMOTION_DATA]

    if any(
        data is None
        for data in (
            auth_data,
            region_data,
            aep_data,
            session_data,
            device_data,
            connect_data,
            mammotion_data,
        )
    ):
        return None

    mammotion_response_data = (
        response_factory(Response[LoginResponseData], mammotion_data)
        if isinstance(mammotion_data, dict)
        else mammotion_data
    )
    mammotion_http = MammotionHTTP()
    mammotion_http.response = mammotion_response_data
    mammotion_http.login_info = (
        LoginResponseData.from_dict(mammotion_response_data.data)
        if isinstance(mammotion_response_data.data, dict)
        else mammotion_response_data.data
    )

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
        dev_by_account=ListingDevAccountResponse.from_dict(device_data)
        if isinstance(device_data, dict)
        else device_data,
        login_by_oauth_response=LoginByOAuthResponse.from_dict(auth_data)
        if isinstance(auth_data, dict)
        else auth_data,
        mammotion_http=mammotion_http,
    )

    await cloud_client.check_or_refresh_session()
    return cloud_client


async def _async_update_listener(
    hass: HomeAssistant, entry: MammotionConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: MammotionConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        for mower in entry.runtime_data.mowers:
            with contextlib.suppress(TimeoutError):
                await mower.api.mammotion.remove_device(mower.name)
    return unload_ok


async def async_remove_config_entry(
    hass: HomeAssistant, entry: MammotionConfigEntry
) -> None:
    """Remove a config entry."""
    await hass.config_entries.async_remove(entry.entry_id)
    store = MammotionConfigStore(hass)
    await store.async_remove()


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: MammotionConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    mower_names = (
        next(
            identifier[1]
            for identifier in device_entry.identifiers
            if identifier[0] == DOMAIN
        ),
    )
    mower = next(
        (
            mower
            for mower in config_entry.runtime_data.mowers
            if mower.name in mower_names
        ),
        None,
    )

    return not bool(mower)
