"""A fake of the sync service, at the library client's public interface.

``FakeClient`` stands in for ``BabyTrackerClient`` (``sign_in``, ``get_devices``,
``get_transactions``, ``post_transaction``, ``close``). The real sync engine runs on top of it, so
the tests exercise the real merging of logs. ``FakeServer`` holds the state behind every client:
devices, their logs, and switches to make a call fail, hang for an interleaving test, let another
device write just before a post, or report a log shorter than it is.
"""

from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime
from types import MappingProxyType
from typing import Any

from pybabytracker import AuthenticationError, Device, RawTransaction

from . import BABY_ONE, PASSWORD
from .factories import OP_ADD, record_payload, wire

PAGE_SIZE = 500


class FakeServer:
    """The state behind every fake client: devices, their logs, and failure switches."""

    def __init__(self) -> None:
        """Set up an empty service."""
        self.password = PASSWORD
        self.logs: dict[str, list[dict[str, Any]]] = {}
        self.names: dict[str, str] = {}
        self.sign_in_error: Exception | None = None
        self.request_error: Exception | None = None
        self.read_errors: dict[str, Exception] = {}
        self.clients: list[FakeClient] = []
        self.sign_ins: list[dict[str, str]] = []
        self.device_list_calls = 0
        self.transaction_reads: list[tuple[str, int]] = []

        self.last_sync_override: dict[str, int] = {}

    def add_record(
        self,
        device: str,
        type_name: str,
        object_id: str,
        *,
        when: datetime,
        baby: Mapping[str, Any] | None = MappingProxyType(BABY_ONE),
        op: int = OP_ADD,
        changed: datetime | None = None,
        note: str = "",
        **fields: Any,
    ) -> int:
        """Add a record to a device's log, and return its sync ID."""
        payload = record_payload(
            type_name,
            object_id,
            when=when,
            baby=baby,
            changed=changed,
            note=note,
            **fields,
        )
        return self.add_payload(device, payload, op=op)

    def add_payload(
        self, device: str, payload: dict[str, Any], *, op: int = OP_ADD
    ) -> int:
        """Add a payload to a device's log, and return its sync ID."""
        log = self.logs.setdefault(device, [])
        sync_id = len(log) + 1
        log.append(wire(sync_id, op, payload))
        self.names.setdefault(device, f"Device {device[:1]}")
        return sync_id

    def listed_devices(self) -> list[Device]:
        """The devices the service lists, each with the length of its log.

        ``last_sync_override`` makes it report a log shorter (or longer) than it is.
        """
        devices = [
            Device(
                device_uuid=uuid,
                last_sync_id=len(log),
                device_name=self.names[uuid],
                device_os_info="test",
            )
            for uuid, log in self.logs.items()
        ]
        listed = {device.device_uuid for device in devices}
        devices += [
            Device(uuid, last, "Home Assistant", "test")
            for uuid, last in self.last_sync_override.items()
            if uuid not in listed
        ]
        return [
            replace(device, last_sync_id=self.last_sync_override[device.device_uuid])
            if device.device_uuid in self.last_sync_override
            else device
            for device in devices
        ]

    @property
    def open_clients(self) -> list[FakeClient]:
        """The clients not yet closed."""
        return [client for client in self.clients if not client.closed]

    def reads_from_start(self) -> list[tuple[str, int]]:
        """The log reads that started from the beginning."""
        return [read for read in self.transaction_reads if read[1] == 0]


class FakeClient:
    """Stands in for ``BabyTrackerClient``."""

    def __init__(
        self,
        server: FakeServer,
        email: str,
        password: str,
        device_uuid: str,
        device_name: str,
        **kwargs: Any,
    ) -> None:
        """Set up a client on the fake service."""
        self.server = server
        self.email = email
        self.password = password
        self.device_uuid = device_uuid
        self.device_name = device_name
        self.kwargs = kwargs
        self.closed = False
        self._signed_in = False
        server.clients.append(self)

    async def sign_in(self) -> int:
        """Sign in, as the real client does."""
        self.server.sign_ins.append(
            {
                "email": self.email,
                "password": self.password,
                "device_uuid": self.device_uuid,
                "device_name": self.device_name,
            }
        )
        if self.server.sign_in_error is not None:
            raise self.server.sign_in_error
        if self.password != self.server.password:
            raise AuthenticationError("the service rejected the email or password")
        self._signed_in = True
        return 1

    async def _ensure_session(self) -> None:
        if self.server.request_error is not None:
            raise self.server.request_error
        if not self._signed_in or self.password != self.server.password:
            await self.sign_in()

    async def get_devices(self) -> list[Device]:
        """List the devices in the sync group."""
        await self._ensure_session()
        self.server.device_list_calls += 1
        return self.server.listed_devices()

    async def get_transactions(
        self, device_uuid: str, since_sync_id: int = 0
    ) -> list[RawTransaction]:
        """Read a page of a device's log after a sync ID."""
        await self._ensure_session()
        if device_uuid in self.server.read_errors:
            raise self.server.read_errors[device_uuid]
        self.server.transaction_reads.append((device_uuid, since_sync_id))
        entries = [
            e
            for e in self.server.logs.get(device_uuid, [])
            if e["SyncID"] > since_sync_id
        ]
        return [
            RawTransaction(e["SyncID"], e["OPCode"], e["Transaction"])
            for e in entries[:PAGE_SIZE]
        ]

    async def close(self) -> None:
        """Close the client."""
        self.closed = True
