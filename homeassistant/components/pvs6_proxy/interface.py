"""Interface/API for PVS6 System."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import socket

from aiohttp.client import ClientError, ClientResponseError, ClientSession
from aiohttp.hdrs import METH_GET
import async_timeout
import pydantic

# from pydantic import BaseModel


class Supervisor(pydantic.BaseModel):
    """Power Supervisor."""

    DETAIL: str
    STATE: str
    STATEDESCR: str
    SERIAL: str
    MODEL: str
    HWVER: str
    SWVER: str
    DEVICE_TYPE: str
    DATATIME: str
    dl_err_count: int
    dl_comm_err: int
    dl_skipped_scans: int
    dl_scan_time: int
    dl_untransmitted: int
    dl_uptime: int
    dl_cpu_load: float
    dl_mem_used: int
    dl_flash_avail: int
    panid: int
    CURTIME: str

    @staticmethod
    def get_device_type():
        """Get Device Type."""
        return "PVS"


class PowerMeterP(pydantic.BaseModel):
    """Power Meter Producer."""

    ISDETAIL: bool
    SERIAL: str
    TYPE: str
    STATE: str
    STATEDESCR: str
    MODEL: str
    DESCR: str
    DEVICE_TYPE: str
    interface: str
    slave: int
    SWVER: str
    PORT: str
    DATATIME: str
    ct_scl_fctr: int
    net_ltea_3phsum_kwh: float
    p_3phsum_kw: float
    q_3phsum_kvar: float
    s_3phsum_kva: float
    tot_pf_rto: float
    freq_hz: float
    i_a: float
    v12_v: float
    CAL0: int
    origin: str
    OPERATION: str
    CURTIME: str

    @staticmethod
    def get_device_type():
        """Get Device Type."""
        return "PVS5-METER-P"


class PowerMeterC(pydantic.BaseModel):
    """Power Meter Consumer."""

    ISDETAIL: bool
    SERIAL: str
    TYPE: str
    STATE: str
    STATEDESCR: str
    MODEL: str
    DESCR: str
    DEVICE_TYPE: str
    interface: str
    slave: int
    SWVER: str
    PORT: str
    DATATIME: str
    ct_scl_fctr: int
    net_ltea_3phsum_kwh: float
    p_3phsum_kw: float
    q_3phsum_kvar: float
    s_3phsum_kva: float
    tot_pf_rto: float
    freq_hz: float
    i1_a: float
    i2_a: float
    v1n_v: float
    v2n_v: float
    v12_v: float
    p1_kw: float
    p2_kw: float
    neg_ltea_3phsum_kwh: float
    pos_ltea_3phsum_kwh: float
    CAL0: int
    origin: str
    OPERATION: str
    CURTIME: str

    @staticmethod
    def get_device_type():
        """Get Device Type."""
        return "PVS5-METER-C"


class Inverter(pydantic.BaseModel):
    """Panel Specific Inverter."""

    ISDETAIL: bool
    SERIAL: str
    TYPE: str
    STATE: str
    STATEDESCR: str
    MODEL: str
    DESCR: str
    DEVICE_TYPE: str
    hw_version: str
    interface: str
    module_serial: str
    slave: int
    SWVER: str
    PORT: str
    MOD_SN: str
    NMPLT_SKU: str
    DATATIME: str
    ltea_3phsum_kwh: float
    p_3phsum_kw: float
    vln_3phavg_v: float
    i_3phsum_a: float
    p_mppt1_kw: float
    v_mppt1_v: float
    i_mppt1_a: float
    t_htsnk_degc: float
    freq_hz: float
    stat_ind: float
    origin: str
    OPERATION: str
    CURTIME: str

    @staticmethod
    def get_device_type():
        """Get Device Type."""
        return "Inverter"


class Devices:
    """Expected devices in system."""

    supervisor: Supervisor
    power_meter_p: PowerMeterP
    power_meter_c: PowerMeterC
    inverters: list[Inverter]

    def __init__(self) -> None:
        """Init."""
        self.inverters = []

    def parse(self, devices):
        """Parse devices from device list."""
        for device in devices["devices"]:
            device_type = device["DEVICE_TYPE"]
            if device_type == Supervisor.get_device_type():
                self.supervisor = Supervisor.parse_obj(device)
            elif device_type == "Power Meter":
                if device["TYPE"] == PowerMeterP.get_device_type():
                    self.power_meter_p = PowerMeterP.parse_obj(device)
                elif device["TYPE"] == PowerMeterC.get_device_type():
                    self.power_meter_c = PowerMeterC.parse_obj(device)
            elif device_type == Inverter.get_device_type():
                inverter = Inverter.parse_obj(device)
                self.inverters.append(inverter)


class PVOutputError(Exception):
    """Generic PVOutput exception."""


class PVOutputConnectionError(PVOutputError):
    """PVOutput connection exception."""


@dataclass
class PVOutput:
    """Main class for handling connections with the PVOutput API."""

    session: ClientSession
    request_timeout: float = 8.0

    async def devices(self) -> Devices:
        """Get device list from PVS6."""
        try:
            async with async_timeout.timeout(self.request_timeout):
                response = await self.session.request(
                    METH_GET, "http://solar-proxy/cgi-bin/dl_cgi?Command=DeviceList"
                )
                response.raise_for_status()
        except asyncio.TimeoutError as exception:
            msg = "Timeout occurred while connecting to the PVOutput API"
            raise PVOutputConnectionError(msg) from exception
        except ClientResponseError as exception:
            msg = "Error occurred while connecting to the PVOutput API"
            raise PVOutputError(msg) from exception
        except (ClientError, socket.gaierror) as exception:
            msg = "Error occurred while communicating with the PVOutput API"
            raise PVOutputConnectionError(msg) from exception
        response = await response.json()
        devices = Devices()
        devices.parse(response)
        return devices
