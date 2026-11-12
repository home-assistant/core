"""A fake panel that speaks the real protocol, for tests that need one to dial in.

Every frame here is assembled with the project's own `build_frame`, so the checksums are real and
the listener has to parse them exactly as it parses a live panel's. That matters for the sprint's
acceptance criterion about three panels of different models on one port: a simulator that produced
approximately-right bytes would prove nothing about the multi-panel path.

Pure standard library and pure `protocol` — no Home Assistant, so it can also be used from the
offline suite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib

from pyjfl import EVENTS_PER_PAGE, Cmd, build_frame

EVENT_RECORD_SIZE = 14
"""Bytes per `0x48` record."""

CONNECTION_LENGTH = 102
STATUS_LENGTH = 127
"""Firmware 7.60 sends 127 bytes, not the 123 the specification documents."""


def _fixed(text: str, length: int, pad: int = 0xFF) -> bytes:
    """Encode *text* into exactly *length* bytes, padded the way the panel pads."""
    raw = text.encode("latin-1")[:length]
    return raw + bytes([pad]) * (length - len(raw))


@dataclass
class FakePanel:
    """Builds the frames a panel of a given model would send.

    Defaults describe the one panel this project can validate against hardware: an Active 32 Duo
    with two programmed partitions and an electric fence.
    """

    serial: str = "0000000001"
    model_byte: int = 0xA0
    firmware: str = "760"
    mac: str = ""
    """Left empty to be derived from the serial. Two panels sharing a MAC is not merely unrealistic
    — Home Assistant's device registry refuses the second device outright, so a test with two
    panels would silently create only one."""

    imei: str = ""
    signal: int = 0

    partitions: list[int] = field(default_factory=lambda: [0x01, 0x01, 0x00, 0x00])
    """`PART[i]`: `0x00` not programmed, `0x01` disarmed, `0x02` away, `0x03` stay, bit 7 alarm."""

    fence: int = 0x01
    """`ELET`. `0x00` means the panel has no electric fence configured."""

    zones: dict[int, int] = field(default_factory=lambda: {1: 0x8, 2: 0x7, 9: 0x1})
    """Zone number to nibble. Anything unlisted is `0x0`, meaning the zone is not in use."""

    problems: bytes = b"\x00\x00\x00\x00\x00"
    battery_raw: int = 0xB7
    """`raw / 14` volts — `0xB7` is 13.07 V, which is what the captured panel reported."""

    pgm: int = 0x00
    pgm_high: int = 0x00
    siren: int = 0x00
    updating: bool = False
    checksum: bytes = b"\x35\x08"
    clock: bytes = b"\x08\x26\x16\x22\x50\x45"
    """BCD: 08/26/16 22:50:45. Every field has to be valid BCD or the decoder renders nonsense."""

    bypassable: bytes = field(default_factory=lambda: bytes(13))

    zone_names: dict[int, str] = field(default_factory=dict)
    """Zone number to programmed name, for the `0x44` reply. Unlisted zones have no name."""

    disabled_zones: set[int] = field(default_factory=set)
    """Zones whose programming attribute byte 0 reads `0x00` — not in use on this installation."""

    partition_names: dict[int, str] = field(default_factory=dict)
    events: list[tuple[int, str, int, int, list[int]]] = field(default_factory=list)
    """The `0x48` buffer, oldest first: `(serial, contact_id, subject, partition, BCD timestamp)`.

    Empty by default, because a panel that has never reported anything is a legitimate state and the
    tests that do not care about history should not have to say so."""

    pgm_names: dict[int, str] = field(default_factory=dict)

    pgm_functions: dict[int, int] = field(default_factory=dict)
    """PGM number to function byte (attribute byte 5 of the record). 18 is the electric fence, 25 is
    the Active 20's silent one. Unset PGMs read `0xFF`, which decodes to no known function."""

    pgm_durations: dict[int, int] = field(default_factory=dict)
    """PGM number to raw duration byte (attribute byte 4). §18.2's scale: 1-200 minutes, 201-255
    seconds minus 200. Unset means the field is left as padding."""

    wireless_devices: dict[int, int] = field(default_factory=dict)
    """Serial to zone number, in enrolment-slot order. A zone listed here is wireless."""

    pgm_permissions: int = 0x0F
    """`P-PGM` at offset 87: PGMs 1-8, **LSB is PGM 1**. `0x0F` is what the captured panel sent."""

    pgm_permissions_high: int = 0x0F
    """`P-PGM2` at offset 118: PGMs 9-16."""

    fence_permissions: int = 0x09
    """`P-ELET`. Bit 0 is "may disarm" and **bit 3**, not bit 1, is "may arm"."""

    partition_permissions: list[int] | None = None
    """`P-PART[i]`, or `None` to grant everything to every programmed partition.

    Worth overriding in any test about a refused command: the capture read `0x0B` for a partition
    that was disarmed — no STAY bit — so "the panel does not allow stay arming here" is a normal
    state of a real installation rather than an exotic one.
    """

    seq: int = 0x10

    def __post_init__(self) -> None:
        """Give a panel with no explicit MAC one that is unique to its serial."""
        if not self.mac:
            digest = hashlib.sha256(self.serial.encode()).hexdigest()[:12]
            self.mac = digest.upper()

    def _next_seq(self) -> int:
        self.seq = 1 if self.seq >= 0xFF else self.seq + 1
        return self.seq

    def connection(self) -> bytes:
        """The `0x21` frame the panel sends the moment it connects."""
        payload = bytearray()
        payload += _fixed(self.serial, 10, pad=0x30)  # NS, absolute 4-13
        payload += _fixed(self.imei, 15)  # IMEI, 14-28
        payload += _fixed(self.mac, 12, pad=0x46)  # MAC, 29-40
        payload += bytes([self.model_byte])  # MOD, 41
        payload += _fixed(self.firmware, 3, pad=0x30)  # VER, 42-44
        payload += bytes([0x02, 0x01, 0x01, 0x06])  # IP/SIM/via/operator, 45-48
        payload += bytes([self.signal, 0x00])  # signal 49, problem 50
        payload += bytes([sum(1 for state in self.partitions if state)])  # 51
        payload += bytes(32)  # accounts, 52-83
        payload += bytes([self.fence])  # SELECT, 84
        payload += bytes(self._partition_bytes())  # SPART, 85-100
        frame = build_frame(self._next_seq(), Cmd.CONNECTION, bytes(payload))
        assert len(frame) == CONNECTION_LENGTH, len(frame)
        return frame

    def status(self) -> bytes:
        """The status frame, which the panel sends only when asked with `0x4D` or `0x56`."""
        payload = bytearray()
        payload += self.checksum  # KP, 4-5
        payload += self.clock  # 6-11
        payload += bytes([self.battery_raw, self.pgm])  # BAT 12, PGM 13
        payload += bytes(self._partition_bytes())  # PART, 14-29
        payload += bytes([self.fence])  # ELET, 30
        payload += self._zone_bytes()  # ZONA, 31-80
        payload += self.problems  # PROB, 81-85
        payload += bytes(
            [self.fence_permissions, self.pgm_permissions]
        )  # P-ELET 86, P-PGM 87
        payload += bytes(self._permission_bytes())  # P-PART, 88-103
        payload += self.bypassable  # P-INIB, 104-116
        payload += bytes(
            [self.pgm_high, self.pgm_permissions_high, 0x00]
        )  # 117, 118, 119
        payload += bytes(
            [self.siren, 0x01 if self.updating else 0x00]
        )  # PA_SIR 120, ATUALIZ 121
        payload += bytes(4)  # the tail firmware 7.60 adds, 122-125
        frame = build_frame(self._next_seq(), Cmd.STATUS, bytes(payload))
        assert len(frame) == STATUS_LENGTH, len(frame)
        return frame

    def event(
        self,
        code: str = "1130",
        partition: str = "01",
        subject: str = "009",
        counter: bytes = b"\x00\x00\x39\x1d",
        account: str = "0001",
    ) -> bytes:
        """A `0x24` Contact ID event."""
        payload = bytearray()
        payload += account.encode()[:4].ljust(4, b"0")  # CONTA, 4-7
        payload += code.encode()[:4].ljust(4, b"0")  # EVENTO, 8-11
        payload += partition.encode()[:2].ljust(2, b"0")  # PARTICAO, 12-13
        payload += subject.encode()[:3].ljust(3, b"0")  # USUA/ZONA, 14-16
        payload += counter[:4].ljust(4, b"\x00")  # CONTADOR, 17-20
        payload += bytes([self.fence, 0x00])  # SPART 21, PROB 22
        return build_frame(self._next_seq(), Cmd.EVENT, bytes(payload))

    def keepalive(self) -> bytes:
        """The `0x40` keep-alive."""
        return build_frame(self._next_seq(), Cmd.KEEP_ALIVE)

    def programming(self, address: int, count: int) -> bytes:
        """The `0x44` reply: the selector echoed, then `KP`, then *count* bytes of programming.

        The memory is synthesised from `zone_names`, `partition_names` and `wireless_devices` rather
        than stored as a blob, so a test can say "zone 3 is called Kitchen" and not "here are 8 KB
        of hex". Anything unset reads `0xFF`, which is exactly what an unprogrammed panel returns.
        """
        payload = bytes([address >> 8, address & 0xFF, count]) + self.checksum
        payload += self._programming_bytes(address, count)
        return build_frame(self._next_seq(), Cmd.READ_PROGRAMMING, payload)

    def wireless_inventory(self, seq: int, page: int) -> bytes:
        """Build a `0x59` reply for *page*, from the same `wireless_devices` the memory uses.

        Synthesised rather than replayed so the two structures agree by construction: a test that
        proved the inventory parses while disagreeing with the enrolment table would be proving the
        wrong thing. Signal and firmware are varied per slot so a test can tell one device's sensor
        from another's.
        """
        per_page = 8
        items = list(self.wireless_devices.items())
        # Pages are zero-based, as ActiveNet numbers them: `59 08 00` is the first eight devices.
        start = page * per_page
        chunk = items[start : start + per_page]
        payload = bytearray([per_page])
        for index, (serial, zone) in enumerate(chunk, start=start + 1):
            payload += bytes(
                [
                    index,
                    *serial.to_bytes(4, "big"),
                    zone,
                    0x40,  # firmware 4.0
                    0x00,  # closed
                    0x09,
                    0x08,
                    0x26,
                    0x17,
                    0x19,
                    0x30,  # last transmission, BCD
                    0x00,  # battery ok
                    0x04
                    if index % 2
                    else 0x13,  # excellent direct / very good via repeater 1
                ]
            )
        payload += bytes(16 * (per_page - len(chunk)))
        return build_frame(seq, Cmd.READ_WIRELESS, bytes(payload))

    def event_buffer(self, seq: int, cursor: int) -> bytes:
        """Answer a `0x48` read: up to eight records with a serial greater than *cursor*.

        Mirrors the real panel's paging exactly — oldest first, forward only, eight per page —
        because that shape is the whole reason the coordinator has to loop, and a simulator that
        returned everything at once would let a broken loop pass.
        """
        page = [record for record in self.events if record[0] > cursor][
            :EVENTS_PER_PAGE
        ]
        payload = bytes([EVENTS_PER_PAGE])
        for serial, code, subject, partition, stamp in page:
            payload += serial.to_bytes(4, "big")
            # Suppressed below rather than switched to `base=0`: `code` is a bare Contact ID digit
            # string with no `0x` prefix to strip (e.g. "3401"), and `int(x, base=0)` raises on one
            # with a leading zero (e.g. "0570") because it reads as an invalid legacy octal literal.
            payload += bytes(
                [int(code[:2], 16), int(code[2:], 16), subject, partition]  # noqa: FURB166
            )
            payload += bytes(stamp)
        # The real panel ends a download with terminator records rather than a short frame —
        # Padding matters: a reply carrying no records at all is
        # below the length the decoder treats as a reply, so an empty buffer would look like
        # silence rather than like an answer.
        payload += b"\xff" * (EVENT_RECORD_SIZE * (EVENTS_PER_PAGE - len(page)))
        return build_frame(seq, Cmd.READ_EVENTS, payload)

    def _programming_bytes(self, address: int, count: int) -> bytes:
        """Render *count* bytes of the synthetic programming space starting at *address*."""
        memory = bytearray(b"\xff" * 0x2000)

        for number, name in self.zone_names.items():
            base = 0x1000 + (number - 1) * 16
            memory[base : base + 9] = name.encode("latin-1")[:9].ljust(9, b"\xff")
            # Attribute byte 0: 0x00 disabled, anything else in use.
            memory[base + 9] = 0x00 if number in self.disabled_zones else 0x10

        for number, name in self.partition_names.items():
            base = 0x006F + 1 + (number - 1) * 9
            memory[base : base + 9] = name.encode("latin-1")[:9].ljust(9, b"\xff")

        for number, name in self.pgm_names.items():
            base = 0x01BF + 1 + (number - 1) * 16
            memory[base : base + 9] = name.encode("latin-1")[:9].ljust(9, b"\xff")

        # Attribute byte 4 is the duration (record byte 13), byte 5 the function (record byte 14).
        for number, function in self.pgm_functions.items():
            base = 0x01BF + 1 + (number - 1) * 16
            memory[base + 14] = function
        for number, duration in self.pgm_durations.items():
            base = 0x01BF + 1 + (number - 1) * 16
            memory[base + 13] = duration

        for slot, (serial, zone) in enumerate(self.wireless_devices.items(), start=1):
            base = 0x1800 + (slot - 1) * 8
            memory[base : base + 4] = serial.to_bytes(4, "big")
            memory[base + 4] = zone

        return bytes(memory[address : address + count]).ljust(count, b"\xff")

    def _partition_bytes(self) -> list[int]:
        """`PART`/`SPART`: always sixteen bytes, whatever the model can really have."""
        states = list(self.partitions[:16])
        return states + [0x00] * (16 - len(states))

    def _permission_bytes(self) -> list[int]:
        """`P-PART`: the override if there is one, else everything for each programmed partition."""
        if self.partition_permissions is not None:
            states = list(self.partition_permissions[:16])
            return states + [0x00] * (16 - len(states))
        return [0x1F if state else 0x00 for state in self._partition_bytes()]

    def _zone_bytes(self) -> bytes:
        """Pack the zone nibbles into fifty bytes, **high nibble first**."""
        packed = bytearray(50)
        for number, nibble in self.zones.items():
            index = (number - 1) // 2
            if index >= 50:
                continue
            if number % 2:
                packed[index] |= (nibble & 0x0F) << 4
            else:
                packed[index] |= nibble & 0x0F
        return bytes(packed)
