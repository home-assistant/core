# Originally authored by @mtdcr
# Ported and modernized for Home Assistant Core as part of the core migration

"""Utility functions for aten_pe."""

from atenpdu import AtenPE
from pysnmp.hlapi.varbinds import MibViewControllerManager


def create_aten_pe_device(
    node: str,
    serv: str,
    community: str,
    username: str,
    authkey: str | None,
    privkey: str | None,
) -> AtenPE:
    """Create and pre-load AtenPE device in the executor thread."""
    dev = AtenPE(
        node=node,
        serv=serv,
        community=community,
        username=username,
        authkey=authkey,
        privkey=privkey,
    )
    # Warm up and compile all MIBs in the background executor thread
    mvc = MibViewControllerManager.get_mib_view_controller(dev._snmp_engine.cache)  # noqa: SLF001
    mvc.mibBuilder.load_modules()
    return dev
