"""Sensor platform for the rtl_433 integration.

Each rtl_433 device transmits a flat set of measurement fields. This platform
creates one :class:`Rtl433Sensor` per (device, field): entities for devices
already recorded on the config entry are built at setup, and entities for
devices/fields first observed at runtime are added as their events arrive and
recorded on the entry so the next startup rebuilds them.

Entity and device identity matches the custom component of the same domain, so
an entry migrated from it keeps its entities. Only that direction is supported:
see ``async_migrate_entry``.

* sensor ``unique_id``  -> ``f"{hub_entry_id}:{device_key}:{object_suffix}"``
* per-device identifier -> ``(DOMAIN, f"{hub_entry_id}:{device_key}")``
* hub ``via_device_id`` -> the hub device registered by ``async_setup_entry``

where ``hub_entry_id == entry.entry_id``, ``device_key`` is the deterministic key
produced by :mod:`pyrtl_433.normalizer`, and ``object_suffix`` is the field key.
"""

from datetime import timedelta
from typing import Any, override

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_DEVICES, CONF_MODEL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DEFAULT_AVAILABILITY_TIMEOUT, DEVICE_FIELDS, DOMAIN, MANUFACTURER
from .coordinator import Rtl433ConfigEntry, Rtl433Coordinator


def _device_name(model: str, device_key: str) -> str:
    """Return a human-readable device name (falls back to the device key)."""
    return model or device_key


@callback
def _persist_devices(
    hass: HomeAssistant,
    entry: Rtl433ConfigEntry,
    sources: dict[str, tuple[str, set[str]]],
) -> None:
    """Merge discovered devices and their fields into ``entry.data[CONF_DEVICES]``.

    Fields are unioned rather than clobbered, and the entry is written only when
    a record actually changes, so a device transmitting every few seconds does
    not rewrite the entry with each event.
    """
    devices: dict[str, dict[str, Any]] = {
        device_key: dict(record)
        for device_key, record in entry.data.get(CONF_DEVICES, {}).items()
    }
    changed = False
    for device_key, (model, fields) in sources.items():
        record = devices.setdefault(device_key, {CONF_MODEL: "", DEVICE_FIELDS: []})
        if model and record.get(CONF_MODEL) != model:
            record[CONF_MODEL] = model
            changed = True
        merged = sorted(set(record.get(DEVICE_FIELDS, [])) | fields)
        if merged != record.get(DEVICE_FIELDS, []):
            record[DEVICE_FIELDS] = merged
            changed = True

    if changed:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_DEVICES: devices}
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Rtl433ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up rtl_433 sensors for the hub config entry."""
    coordinator = entry.runtime_data
    hub_entry_id = entry.entry_id
    created: set[str] = set()

    @callback
    def _discover() -> None:
        """Create sensors for any device/field not seen before."""
        # Union the persisted devices map (recreated on startup, survives before
        # a device next transmits) with the fields seen live this session.
        sources: dict[str, tuple[str, set[str]]] = {}
        for device_key, record in entry.data.get(CONF_DEVICES, {}).items():
            sources[device_key] = (
                record.get(CONF_MODEL, ""),
                set(record.get(DEVICE_FIELDS, [])),
            )
        for device_key, event in (coordinator.data or {}).items():
            model, fields = sources.get(device_key, ("", set()))
            sources[device_key] = (model or event.model, fields | set(event.fields))
        _persist_devices(hass, entry, sources)

        new_entities: list[Rtl433Sensor] = []
        for device_key, (model, fields) in sources.items():
            for field_key in fields:
                unique_id = f"{hub_entry_id}:{device_key}:{field_key}"
                if unique_id in created:
                    continue
                created.add(unique_id)
                new_entities.append(
                    Rtl433Sensor(coordinator, device_key, model, field_key)
                )
        if new_entities:
            async_add_entities(new_entities)

    _discover()
    entry.async_on_unload(coordinator.async_add_listener(_discover))


class Rtl433Sensor(CoordinatorEntity[Rtl433Coordinator], SensorEntity):
    """A single measurement field of one rtl_433 device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: Rtl433Coordinator,
        device_key: str,
        model: str,
        field_key: str,
    ) -> None:
        """Initialize identity, device info, and the entity name."""
        super().__init__(coordinator)
        self._device_key = device_key
        self._field_key = field_key

        hub_entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{hub_entry_id}:{device_key}:{field_key}"
        self._attr_name = field_key.replace("_", " ")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{hub_entry_id}:{device_key}")},
            name=_device_name(model, device_key),
            model=model or None,
            manufacturer=MANUFACTURER,
            via_device_id=dr.async_get_device_id_by_identifier(
                coordinator.hass,
                (DOMAIN, hub_entry_id),
                config_entry_id=hub_entry_id,
            ),
        )

    @property
    @override
    def native_value(self) -> StateType:
        """Return the field's latest value from the coordinator's last event."""
        event = self.coordinator.data.get(self._device_key)
        if event is None:
            return None
        return event.fields.get(self._field_key)

    @property
    @override
    def available(self) -> bool:
        """Return whether the device was seen within the availability window."""
        if not self.coordinator.last_update_success:
            return False
        last_seen = self.coordinator.last_seen.get(self._device_key)
        if last_seen is None:
            return False
        return dt_util.utcnow() - last_seen <= timedelta(
            seconds=DEFAULT_AVAILABILITY_TIMEOUT
        )
