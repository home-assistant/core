"""Klyqa datacoordinator."""
import asyncio
from datetime import timedelta
import logging
import socket
from typing import Any

from klyqa_ctl import klyqa_ctl as api

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_component import (
    DEFAULT_SCAN_INTERVAL,
    EntityComponent,
)

from .const import (
    CONF_POLLING,
    CONF_SYNC_ROOMS,
    DOMAIN,
    EVENT_KLYQA_NEW_LIGHT,
    EVENT_KLYQA_NEW_LIGHT_GROUP,
    LOGGER,
)


class HAKlyqaAccount(api.Klyqa_account):
    """HAKlyqaAccount"""

    hass: HomeAssistant

    udp: socket.socket
    tcp: socket.socket
    polling: bool
    sync_rooms: bool
    scan_interval_conf: float

    def __init__(
        self,
        udp,
        tcp,
        username="",
        password="",
        host="",
        hass=None,
        polling=True,
        sync_rooms=True,
        scan_interval=-1.0,
    ):
        super().__init__(username, password, host)
        self.hass = hass
        self.udp = udp
        self.tcp = tcp
        self.polling = polling
        self.sync_rooms = sync_rooms
        self.scan_interval_conf = scan_interval

    async def send_to_bulbs(
        self, args, args_in, async_answer_callback=None, timeout_ms=5000
    ):
        """_send_to_bulbs"""
        ret = await super()._send_to_bulbs(
            args,
            args_in,
            self.udp,
            self.tcp,
            async_answer_callback=async_answer_callback,
            timeout_ms=timeout_ms,
        )
        return ret

    async def login(self, **kwargs: Any) -> bool:
        ret = await super().login(**kwargs)
        if ret:
            integration_data, cached = await api.async_json_cache(
                {
                    CONF_USERNAME: self.username,
                    CONF_PASSWORD: self.password,
                    CONF_SCAN_INTERVAL: self.scan_interval_conf,
                    CONF_SYNC_ROOMS: self.sync_rooms,
                    CONF_POLLING: self.polling,
                    CONF_HOST: self.host,
                },
                "last.klyqa_integration_data.cache.json",
            )
        return ret

    async def update_account(self):
        """update_account"""

        await self.request_account_settings()
        if EVENT_KLYQA_NEW_LIGHT in self.hass.bus._listeners:
            ha_entities = self.hass.data["light"].entities

            for device in self.acc_settings["devices"]:
                # look if any onboarded device is not in the entity registry already
                u_id = api.format_uid(device["localDeviceId"])

                light = [
                    entity
                    for entity in ha_entities
                    if hasattr(entity, "u_id") and entity.u_id == u_id
                ]

                if len(light) == 0:
                    if device["productId"].startswith("@klyqa.lighting"):
                        """found klyqa device not in the light entities"""
                        self.hass.bus.fire(EVENT_KLYQA_NEW_LIGHT, device)

            for group in self.acc_settings["deviceGroups"]:
                u_id = api.format_uid(group["id"])

                light = [
                    entity
                    for entity in ha_entities
                    if hasattr(entity, "u_id") and entity.u_id == u_id
                ]

                if len(light) == 0:
                    """found klyqa device not in the light entities"""
                    if (
                        len(group["devices"]) > 0
                        and "productId" in group["devices"][0]
                        and group["devices"][0]["productId"].startswith(
                            "@klyqa.lighting"
                        )
                    ):
                        self.hass.bus.fire(EVENT_KLYQA_NEW_LIGHT_GROUP, group)
        return True


class KlyqaDataCoordinator(EntityComponent):
    """KlyqaDataCoordinator"""

    _instance = None
    KlyqaAccounts: dict[str, HAKlyqaAccount]
    udp: socket.socket
    tcp: socket.socket
    remove_listeners: list

    def __init__(self):
        raise RuntimeError("Call instance() instead")

    def get_ports(self):
        """__get_ports"""
        try:
            self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_address = ("0.0.0.0", 2222)
            self.udp.bind(server_address)
            LOGGER.debug("Bound UDP port 2222")

        except:
            LOGGER.error(
                "Error on opening and binding the udp port 2222 on host for initiating the lamp communication."
            )
            return 1

        try:
            self.tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_address = ("0.0.0.0", 3333)
            self.tcp.bind(server_address)
            LOGGER.debug("Bound TCP port 3333")
            self.tcp.listen(1)

        except:
            LOGGER.error(
                "Error on opening and binding the tcp port 3333 on host for initiating the lamp communication."
            )
            return 1

    def init(
        self,
        logger: logging.Logger,
        domain: str,
        hass: HomeAssistant,
        scan_interval: timedelta = DEFAULT_SCAN_INTERVAL,
    ):
        """__init"""
        print("Init new instance")
        super().__init__(logger, domain, hass, scan_interval)
        self.KlyqaAccounts = {}
        self.get_ports()

        self.entries = {}
        self.remove_listeners = []

    @classmethod
    def instance(
        cls,
        logger: logging.Logger,
        domain: str,
        hass: HomeAssistant,
        scan_interval: timedelta = DEFAULT_SCAN_INTERVAL,
    ):
        """instance"""
        if cls._instance is None:
            print("Creating new instance")
            cls._instance = cls.__new__(cls)
            # Put any initialization here.
            cls._instance.init(logger, domain, hass, scan_interval)
        return cls._instance
