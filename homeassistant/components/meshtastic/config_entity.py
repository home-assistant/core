"""Shared plumbing for the Meshtastic configuration entities.

Only settings the firmware applies **live** are exposed as entities.  Every
other configuration write reboots the radio, and an entity that reboots a radio
when a switch is flipped is a trap, so those settings are deliberately absent.

The rule lives in the firmware's single save funnel,
``AdminModule::saveChanges(int saveWhat, bool shouldReboot = true)``
(``AdminModule.h:44``), which schedules ``reboot(DEFAULT_REBOOT_SECONDS)`` —
seven seconds (``configuration.h:371``) — unless the handler passes ``false``.
``handleSetConfig`` (``AdminModule.cpp:635-906``) starts with
``requiresReboot = true`` and only clears it when none of a per-section list of
fields changed.  The matrix below was transcribed from that function and
verified against firmware ``v2.7.26.54e0d8d``:

| Section          | Reboots when                                     | Exposed here |
|------------------|--------------------------------------------------|--------------|
| ``lora``         | ``use_preset``, ``region``, ``modem_preset``,    | the live     |
|                  | ``bandwidth``, ``spread_factor``,                | fields only  |
|                  | ``coding_rate``, ``tx_power``,                   |              |
|                  | ``frequency_offset``, ``override_frequency``,    |              |
|                  | ``channel_num`` or                               |              |
|                  | ``sx126x_rx_boosted_gain`` changes               |              |
| ``device``       | ``button_gpio``, ``buzzer_gpio``, ``role`` or    | the live     |
|                  | ``rebroadcast_mode`` changes                     | fields only  |
| ``position``     | always                                           | no           |
| ``network``      | always                                           | no           |
| ``bluetooth``    | always                                           | no           |
| ``device_ui``    | always, and stores nothing                       | no           |
| ``power``        | every field this integration would want          | no           |
| ``display``      | ``screen_on_secs``, ``flip_screen``, ``oled``,   | no           |
|                  | ``displaymode``                                  |              |
| ``security``     | ``debug_log_api_enabled``, ``serial_enabled``;   | no           |
|                  | ``is_managed`` locks out local administration    |              |
| module configs   | always, including value-identical writes,        | no           |
|                  | except ``statusmessage``                         |              |

``sx126x_rx_boosted_gain`` is on the *rebooting* side of the LoRa list, so it is
not a switch here even though it looks like one; :func:`assert_live` refuses it.

Two more rules from the same investigation are implemented below:

* Writes replace a whole section.  The firmware copies the received
  ``Config.<Section>`` over its own, so a write must start from the section the
  node last reported, change one field and send the rest back untouched.
* Every ``set_config`` writes flash even when nothing changed, so an unchanged
  value is not sent at all.
"""

import asyncio
from collections.abc import Callable, Mapping
from typing import Any, Final, NamedTuple, override

from homeassistant.const import EntityCategory
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.exceptions import ServiceValidationError

from .client import MeshtasticRequestError, raise_for_result
from .const import DOMAIN, LOGGER, PORTNUM_ADMIN_APP, PORTNUM_UNKNOWN_APP
from .coordinator import MeshtasticConfigEntry, MeshtasticCoordinator
from .entity import MeshtasticEntity
from .models import RequestKind

type ConfigValue = bool | int | str

#: ``Config`` sections this module is allowed to touch.
SECTION_LORA: Final = "lora"
SECTION_DEVICE: Final = "device"

#: Fields the firmware applies without rebooting, per section.  This is an
#: allow-list on purpose: a field that is not in it is refused rather than
#: silently rebooting the node.
LIVE_FIELDS: Final[Mapping[str, frozenset[str]]] = {
    SECTION_LORA: frozenset(
        {
            "config_ok_to_mqtt",
            "hop_limit",
            "ignore_mqtt",
            "override_duty_cycle",
            "pa_fan_disabled",
            "tx_enabled",
        }
    ),
    SECTION_DEVICE: frozenset(
        {
            "buzzer_mode",
            "disable_triple_click",
            "double_tap_as_button_press",
            "led_heartbeat_disabled",
            "node_info_broadcast_secs",
            "tzdef",
        }
    ),
}

#: Fields of the same sections whose change makes the node reboot.  Only used to
#: give a precise error; anything outside ``LIVE_FIELDS`` is refused anyway.
REBOOTING_FIELDS: Final[Mapping[str, frozenset[str]]] = {
    SECTION_LORA: frozenset(
        {
            "bandwidth",
            "channel_num",
            "coding_rate",
            "frequency_offset",
            "modem_preset",
            "override_frequency",
            "region",
            "spread_factor",
            "sx126x_rx_boosted_gain",
            "tx_power",
            "use_preset",
        }
    ),
    SECTION_DEVICE: frozenset(
        {"button_gpio", "buzzer_gpio", "rebroadcast_mode", "role"}
    ),
}

#: ``Config.DeviceConfig.BuzzerMode``, by enum number.  Kept here rather than
#: read from the protobuf so that the option list is stable and translatable.
BUZZER_MODES: Final[tuple[str, ...]] = (
    "all_enabled",
    "disabled",
    "notifications_only",
    "system_only",
    "direct_msg_only",
)

#: The library's ``Node.reboot()`` default, and what the firmware logs.
REBOOT_DELAY_SECONDS: Final = 10


class SentPacket(NamedTuple):
    """The packet id of an admin message the library did not hand back.

    ``Node.writeConfig()`` sends the ``AdminMessage`` but returns ``None``, so
    the id has to be read from the interface's own counter, which is the value
    ``MeshInterface._generatePacketId()`` just assigned to that packet.  The
    client only needs an object with an ``id``.
    """

    id: int


@callback
def assert_live(section: str, field: str) -> None:
    """Raise unless the firmware applies this field without a reboot."""
    if field in LIVE_FIELDS.get(section, frozenset()):
        return
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="setting_reboots_node",
        translation_placeholders={"setting": f"{section}.{field}"},
    )


class MeshtasticConfigSnapshot:
    """The gateway's live configuration, as the node last reported it.

    The library downloads the node's whole configuration when it connects and
    keeps it on ``interface.localNode.localConfig``.  Reading it costs nothing
    on the mesh, so the snapshot is refreshed on setup and again whenever the
    link comes back, which is also when the firmware may have clamped a value
    it did not like.
    """

    def __init__(self, coordinator: MeshtasticCoordinator) -> None:
        """Initialise an empty snapshot for one config entry."""
        self.coordinator = coordinator
        self._values: dict[tuple[str, str], ConfigValue] = {}
        self._listeners: list[CALLBACK_TYPE] = []
        self._lock = asyncio.Lock()
        self._loaded = False
        # Where the link stands right now, so the first coordinator update
        # after setup is not mistaken for a reconnect and does not re-read a
        # configuration that was just read.
        self._connected = coordinator.client.connected

    def value(self, section: str, field: str) -> ConfigValue | None:
        """Return the last known value of one setting."""
        return self._values.get((section, field))

    @callback
    def async_add_listener(self, listener: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Subscribe to snapshot changes and return the unsubscribe callback."""
        self._listeners.append(listener)

        @callback
        def _remove() -> None:
            self._listeners.remove(listener)

        return _remove

    async def async_load(self) -> None:
        """Read the configuration once, however many platforms ask for it."""
        async with self._lock:
            if self._loaded:
                return
            self._loaded = True
            await self._async_read()

    @callback
    def async_handle_coordinator_update(self) -> None:
        """Re-read the configuration after the link came back.

        A rebooting write made elsewhere (an action, the phone app) can leave
        the node with clamped values, so the cached copy is refetched rather
        than trusted across a reconnect.
        """
        connected = self.coordinator.client.connected
        was_connected, self._connected = self._connected, connected
        if not connected or was_connected or not self._loaded:
            return
        self.coordinator.config_entry.async_create_task(
            self.coordinator.hass, self._async_read(), f"{DOMAIN} read config"
        )

    async def async_write(self, section: str, field: str, value: ConfigValue) -> None:
        """Change one field of one section and wait for the node's answer.

        The whole section is sent back, because that is what the firmware
        replaces.  A value that is already set is not written at all: every
        ``set_config`` costs a flash write.
        """
        assert_live(section, field)
        client = self.coordinator.client
        gateway = self.coordinator.gateway

        def _send(interface: Any) -> SentPacket | None:
            local_node = interface.localNode
            local_config = getattr(local_node, "localConfig", None)
            if local_config is None:
                raise MeshtasticRequestError(
                    translation_domain=DOMAIN, translation_key="no_config"
                )
            current = getattr(local_config, section)
            if getattr(current, field) == value:
                return None
            setattr(current, field, value)
            local_node.writeConfig(section)
            return SentPacket(id=interface.currentPacketId)

        result = await client.async_request(
            kind=RequestKind.ADMIN_LOCAL_SET,
            portnum=PORTNUM_ADMIN_APP,
            destination=gateway.node_num,
            send=_send,
            want_ack=True,
        )
        if result.packet_id:
            raise_for_result(result, node=gateway.name)
        self._values[(section, field)] = value
        self._async_notify()

    async def _async_read(self) -> None:
        """Copy the sections we expose out of the library's downloaded config.

        Nothing is transmitted: the callback only reads the interface, so the
        client hands back a result with no packet id, which is exactly what a
        send that produced no packet looks like.
        """
        values: dict[tuple[str, str], ConfigValue] = {}

        def _read(interface: Any) -> None:
            local_config = getattr(interface.localNode, "localConfig", None)
            if local_config is None:
                return
            for section, fields in LIVE_FIELDS.items():
                message = getattr(local_config, section, None)
                if message is None:
                    continue
                for field in fields:
                    values[(section, field)] = getattr(message, field)

        try:
            await self.coordinator.client.async_request(
                kind=RequestKind.ADMIN_LOCAL_GET,
                # Nothing goes on the air, so no port owes the firmware any
                # pacing; the unknown port is the one with no send spacing.
                portnum=PORTNUM_UNKNOWN_APP,
                destination=self.coordinator.gateway.node_num,
                send=_read,
                want_ack=False,
            )
        except (MeshtasticRequestError, ServiceValidationError) as err:
            LOGGER.debug("Could not read the node configuration: %s", err)
            return
        self._values = values
        self._async_notify()

    @callback
    def _async_notify(self) -> None:
        """Tell every entity that the snapshot changed."""
        for listener in list(self._listeners):
            listener()


_SNAPSHOTS: Final[dict[str, MeshtasticConfigSnapshot]] = {}


async def async_get_config_snapshot(
    entry: MeshtasticConfigEntry,
) -> MeshtasticConfigSnapshot:
    """Return the configuration snapshot shared by one entry's platforms."""
    if (snapshot := _SNAPSHOTS.get(entry.entry_id)) is None:
        coordinator = entry.runtime_data.coordinator
        snapshot = _SNAPSHOTS[entry.entry_id] = MeshtasticConfigSnapshot(coordinator)
        entry_id = entry.entry_id

        @callback
        def _forget() -> None:
            """Drop the snapshot when the entry unloads."""
            _SNAPSHOTS.pop(entry_id, None)

        entry.async_on_unload(_forget)
        entry.async_on_unload(
            coordinator.async_add_listener(snapshot.async_handle_coordinator_update)
        )
    await snapshot.async_load()
    return snapshot


class MeshtasticConfigEntity(MeshtasticEntity):
    """Base for a gateway setting the firmware applies without rebooting."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: MeshtasticCoordinator,
        snapshot: MeshtasticConfigSnapshot,
        *,
        key: str,
        section: str,
        field: str,
    ) -> None:
        """Initialise a gateway configuration entity."""
        super().__init__(coordinator, key)
        self.snapshot = snapshot
        self.section = section
        self.field = field

    @override
    async def async_added_to_hass(self) -> None:
        """Follow the configuration snapshot as well as the coordinator."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.snapshot.async_add_listener(self.async_write_ha_state)
        )

    @property
    def config_value(self) -> ConfigValue | None:
        """Return the node's current value for this setting."""
        return self.snapshot.value(self.section, self.field)

    async def async_write_config(self, value: ConfigValue) -> None:
        """Write one value and let the node confirm it before showing it."""
        await self.snapshot.async_write(self.section, self.field, value)


async def async_send_admin(
    coordinator: MeshtasticCoordinator, send: Callable[[Any], Any]
) -> None:
    """Send one admin message to the gateway and raise unless it is acked."""
    gateway = coordinator.gateway
    result = await coordinator.client.async_request(
        kind=RequestKind.ADMIN_LOCAL_SET,
        portnum=PORTNUM_ADMIN_APP,
        destination=gateway.node_num,
        send=send,
        want_ack=True,
    )
    raise_for_result(result, node=gateway.name)
