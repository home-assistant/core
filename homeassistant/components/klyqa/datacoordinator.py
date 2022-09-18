"""Klyqa datacoordinator."""
from __future__ import annotations

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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import (
    DEFAULT_SCAN_INTERVAL,
    EntityComponent,
)

from .const import (
    CONF_POLLING,
    CONF_SYNC_ROOMS,
    EVENT_KLYQA_NEW_LIGHT,
    EVENT_KLYQA_NEW_LIGHT_GROUP,
    LOGGER,
)


class HAKlyqaAccount(api.Klyqa_account):  # type: ignore[misc]
    """HAKlyqaAccount."""

    hass: HomeAssistant | None

    udp: socket.socket
    tcp: socket.socket
    polling: bool
    sync_rooms: bool
    scan_interval_conf: float

    def __init__(
        self,
        udp: Any,
        tcp: Any,
        username: str = "",
        password: str = "",
        host: str = "",
        hass: HomeAssistant | None = None,
        polling: bool = True,
        sync_rooms: bool = True,
        scan_interval: float = -1.0,
    ) -> None:
        """HAKlyqaAccount."""
        super().__init__(username, password, host)
        self.hass = hass
        self.udp = udp
        self.tcp = tcp
        self.polling = polling
        self.sync_rooms = sync_rooms
        self.scan_interval_conf = scan_interval

    async def send_to_bulbs(
        self,
        args_parsed: Any,
        args_in: Any,
        timeout_ms: Any = 5000,
        async_answer_callback: Any = None,
    ) -> Any:
        """Send_to_bulbs."""
        ret = await super()._send_to_bulbs(
            args_parsed,
            args_in,
            self.udp,
            self.tcp,
            timeout_ms=timeout_ms,
            async_answer_callback=async_answer_callback,
        )
        return ret

    # pylint: disable=arguments-differ
    async def login(self, **kwargs: Any) -> bool:
        """Login."""
        ret: bool = await super().login(**kwargs)
        if ret:
            await api.async_json_cache(
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

    async def update_account(self) -> bool:
        """Update_account."""

        await self.request_account_settings()
        if (
            self.hass
            and EVENT_KLYQA_NEW_LIGHT
            in self.hass.bus._listeners  # pylint: disable=protected-access
        ):
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
                        # found klyqa device not in the light entities
                        self.hass.bus.fire(EVENT_KLYQA_NEW_LIGHT, device)

            for group in self.acc_settings["deviceGroups"]:
                u_id = api.format_uid(group["id"])

                light = [
                    entity
                    for entity in ha_entities
                    if hasattr(entity, "u_id") and entity.u_id == u_id
                ]

                if len(light) == 0:
                    # found klyqa device not in the light entities
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
    """KlyqaDataCoordinator."""

    _instance = None
    klyqa_accounts: dict[str, HAKlyqaAccount]
    udp: socket.socket
    tcp: socket.socket
    remove_listeners: list
    entries: dict[Any, Any]

    # pylint: disable = super-init-not-called
    def __init__(self) -> None:
        """KlyqaDataCoordinator."""
        raise RuntimeError("Call instance() instead")

    def get_ports(self) -> int:
        """Get_ports."""
        try:
            self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_address = ("0.0.0.0", 2222)
            self.udp.bind(server_address)
            LOGGER.debug("Bound UDP port 2222")

        except:  # noqa: E722 pylint: disable=bare-except
            LOGGER.error(
                "Error on opening and binding the udp port 2222 on host for initiating the lamp communication"
            )
            return 1

        try:
            self.tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_address = ("0.0.0.0", 3333)
            self.tcp.bind(server_address)
            LOGGER.debug("Bound TCP port 3333")
            self.tcp.listen(1)

        except:  # noqa: E722 pylint: disable=bare-except
            LOGGER.error(
                "Error on opening and binding the tcp port 3333 on host for initiating the lamp communication"
            )
            return 1
        return 0

    def init(
        self,
        logger: logging.Logger,
        domain: str,
        hass: HomeAssistant,
        scan_interval: timedelta = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """__init."""
        print("Init new instance")
        super().__init__(logger, domain, hass, scan_interval)
        self.klyqa_accounts = {}
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
    ) -> KlyqaDataCoordinator:
        """Instance."""
        if cls._instance is None:
            print("Creating new instance")
            cls._instance = cls.__new__(cls)
            # Put any initialization here.
            cls._instance.init(logger, domain, hass, scan_interval)
        return cls._instance
