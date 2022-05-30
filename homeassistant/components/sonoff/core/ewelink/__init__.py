import asyncio
import logging
import time
from typing import Dict, List, Callable

from aiohttp import ClientSession

from .base import XRegistryBase, XDevice, SIGNAL_UPDATE, SIGNAL_CONNECTED
from .cloud import XRegistryCloud
from .local import XRegistryLocal, decrypt

_LOGGER = logging.getLogger(__name__)

SIGNAL_ADD_ENTITIES = "add_entities"


class XRegistry(XRegistryBase):
    config: dict = None
    task: asyncio.Task = None

    def __init__(self, session: ClientSession):
        super().__init__(session)

        self.devices: Dict[str, XDevice] = {}

        self.cloud = XRegistryCloud(session)
        self.cloud.dispatcher_connect(SIGNAL_CONNECTED, self.cloud_connected)
        self.cloud.dispatcher_connect(SIGNAL_UPDATE, self.cloud_update)

        self.local = XRegistryLocal(session)
        self.local.dispatcher_connect(SIGNAL_UPDATE, self.local_update)

    def setup_devices(self, devices: List[XDevice]) -> list:
        from ..devices import get_spec

        entities = []

        for device in devices:
            did = device["deviceid"]
            try:
                device.update(self.config["devices"][did])
            except Exception:
                pass

            try:
                uiid = device['extra']['uiid']
                _LOGGER.debug(f"{did} UIID {uiid:04} | %s", device["params"])

                # at this moment entities can catch signals with device_id and
                # update their states, but they can be added to hass later
                entities += [cls(self, device) for cls in get_spec(device)]

                self.devices[did] = device

            except Exception as e:
                _LOGGER.warning(f"{did} !! can't setup device", exc_info=e)

        return entities

    async def stop(self, *args):
        self.devices.clear()
        self.dispatcher.clear()

        await self.cloud.stop()
        await self.local.stop()

        if self.task:
            self.task.cancel()

    async def send(
            self, device: XDevice, params: dict = None,
            params_lan: dict = None, query_cloud: bool = True
    ):
        """Send command to device with LAN and Cloud. Usual params are same.

        LAN will send new device state after update command, Cloud - don't.

        :param device: device object
        :param params: non empty to update state, empty to query state
        :param params_lan: optional if LAN params different (ex iFan03)
        :param query_cloud: optional query Cloud state after update state,
          ignored if params empty
        """
        seq = self.sequence()

        can_local = self.local.online and device.get('host')
        can_cloud = self.cloud.online and device.get('online')

        if can_local and can_cloud:
            # try to send a command locally (wait no more than a second)
            ok = await self.local.send(device, params_lan or params, seq, 1)

            # otherwise send a command through the cloud
            if ok != 'online':
                ok = await self.cloud.send(device, params, seq)
                if ok != 'online':
                    asyncio.create_task(self.check_offline(device))
                elif query_cloud and params:
                    # force update device actual status
                    await self.cloud.send(device, timeout=0)

        elif can_local:
            ok = await self.local.send(device, params_lan or params, seq, 5)
            if ok != 'online':
                asyncio.create_task(self.check_offline(device))

        elif can_cloud:
            ok = await self.cloud.send(device, params, seq)
            if ok == "online" and query_cloud and params:
                await self.cloud.send(device, timeout=0)

        else:
            return

        # TODO: response state
        # self.dispatcher_send(device["deviceid"], state)

    async def send_bulk(self, device: XDevice, params: dict):
        assert "switches" in params

        if "params_bulk" in device:
            for new in params["switches"]:
                for old in device["params_bulk"]["switches"]:
                    # check on duplicates
                    if new["outlet"] == old["outlet"]:
                        old["switch"] = new["switch"]
                        break
                else:
                    device["params_bulk"]["switches"].append(new)
            return

        device["params_bulk"] = params
        await asyncio.sleep(0.1)

        return await self.send(device, device.pop("params_bulk"))

    async def check_offline(self, device: XDevice):
        if not device.get("host"):
            return

        ok = await self.local.send(device, {"cmd": "info"}, timeout=15)
        if ok == "online":
            return

        device.pop("host", None)

        did = device["deviceid"]
        _LOGGER.debug(f"{did} !! Local4 | Device offline")
        self.dispatcher_send(did)

    def cloud_connected(self):
        for deviceid in self.devices.keys():
            self.dispatcher_send(deviceid)

        if self.cloud.online and (not self.task or self.task.done()):
            self.task = asyncio.create_task(self.pow_helper())

    def cloud_update(self, msg: dict):
        did = msg["deviceid"]
        device = self.devices.get(did)
        # the device may be from another Home - skip it
        if not device or "online" not in device:
            return

        params = msg["params"]

        _LOGGER.debug(f"{did} <= Cloud3 | %s | {msg.get('sequence')}", params)

        # process online change
        if "online" in params:
            device["online"] = params["online"]
            # check if LAN online after cloud offline
            if not device["online"] and device.get("host"):
                asyncio.create_task(self.check_offline(device))

        elif device["online"] is False:
            device["online"] = True

        if "sledOnline" in params:
            device["params"]["sledOnline"] = params["sledOnline"]

        self.dispatcher_send(did, params)

    def local_update(self, msg: dict):
        did: str = msg["deviceid"]
        device: XDevice = self.devices.get(did)
        params: dict = msg.get("params")
        if not device:
            if not params:
                try:
                    msg["params"] = params = self.local.decrypt_msg(
                        msg, self.config["devices"][did]["devicekey"]
                    )
                except Exception:
                    _LOGGER.debug(f"{did} !! skip setup for encrypted device")
                    self.devices[did] = msg
                    return

            from ..devices import setup_diy
            device = setup_diy(msg)
            entities = self.setup_devices([device])
            self.dispatcher_send(SIGNAL_ADD_ENTITIES, entities)

        elif not params:
            if "devicekey" not in device:
                return
            try:
                params = self.local.decrypt_msg(msg, device["devicekey"])
            except Exception as e:
                _LOGGER.debug("Can't decrypt message", exc_info=e)
                return

        elif "devicekey" in device:
            # unencripted device with devicekey in config, this means that the
            # DIY device is still connected to the ewelink account
            device.pop("devicekey")

        _LOGGER.debug(f"{did} <= Local3 | %s | {msg.get('seq', '')}", params)

        # msg from zeroconf ServiceStateChange.Removed
        if params.get("online") is False:
            asyncio.create_task(self.check_offline(device))
            return

        if "sledOnline" in params:
            device["params"]["sledOnline"] = params["sledOnline"]

        if device.get("host") != msg.get("host"):
            # params for custom sensor
            device["host"] = params["host"] = msg["host"]
            device["localtype"] = msg["localtype"]

        self.dispatcher_send(did, params)

    async def pow_helper(self):
        from ..devices import POW_UI_ACTIVE

        # collect pow devices
        devices = [
            device for device in self.devices.values()
            if "extra" in device and device["extra"]["uiid"] in POW_UI_ACTIVE
        ]
        if not devices:
            return

        while True:
            if not self.cloud.online:
                await asyncio.sleep(60)
                continue

            ts = time.time()

            for device in devices:
                if not device.get("online") or device.get("pow_ts", 0) > ts:
                    continue

                dt, params = POW_UI_ACTIVE[device["extra"]["uiid"]]
                device["pow_ts"] = ts + dt
                await self.cloud.send(device, params, timeout=0)

            # sleep for 150 seconds (because minimal uiActive - 180 seconds)
            await asyncio.sleep(150)
