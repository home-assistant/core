"""Support for EnOcean select entities (integration-local enum configuration)."""

from __future__ import annotations

from enocean_async import EURID, EnumOptions, Gateway, Observation, SenderAddress

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import EnOceanConfigEntry
from .const import DOMAIN
from .entity import LIB_ENTITY_CATEGORY_MAP, EnOceanEntity

PARALLEL_UPDATES = 1

_LEARNING_SENDER_ENTITY_ID = "learning_sender"
_SENDER_SLOT_ENTITY_ID = "sender_slot"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    gateway: Gateway = config_entry.runtime_data
    gateway_eurid = gateway.eurid

    entities: list[
        EnOceanSelect | EnOceanDeviceSenderSlotSelect | EnOceanLearningSenderSelect
    ] = []
    for eurid, spec in gateway.device_specs.items():
        is_actuator = any(entity.actions for entity in spec.entities)
        for entity in spec.entities:
            if not isinstance(entity.config_spec, EnumOptions):
                continue
            if entity.id == _SENDER_SLOT_ENTITY_ID and not is_actuator:
                continue
            category = LIB_ENTITY_CATEGORY_MAP.get(entity.category)
            if entity.id == _SENDER_SLOT_ENTITY_ID:
                entities.append(
                    EnOceanDeviceSenderSlotSelect(eurid, entity.id, gateway, category)
                )
            else:
                entities.append(
                    EnOceanSelect(
                        eurid, entity.id, gateway, entity.config_spec, category
                    )
                )

    if gateway_eurid is not None:
        for entity in gateway.gateway_entities:
            if not isinstance(entity.config_spec, EnumOptions):
                continue
            category = LIB_ENTITY_CATEGORY_MAP.get(entity.category)
            if entity.id == _LEARNING_SENDER_ENTITY_ID:
                entities.append(
                    EnOceanLearningSenderSelect(
                        gateway_eurid, entity.id, gateway, category
                    )
                )
            else:
                entities.append(
                    EnOceanSelect(
                        gateway_eurid,
                        entity.id,
                        gateway,
                        entity.config_spec,
                        category,
                        is_gateway_config=True,
                    )
                )

    async_add_entities(entities)


class EnOceanSelect(EnOceanEntity, SelectEntity, RestoreEntity):
    """Representation of an EnOcean enum config entity."""

    def __init__(
        self,
        address: EURID,
        entity_key: str,
        gateway: Gateway,
        enum_options: EnumOptions,
        entity_category: EntityCategory | None,
        is_gateway_config: bool = False,
    ) -> None:
        """Initialize the EnOcean select entity."""
        super().__init__(address, entity_key, gateway)
        self._attr_options = list(enum_options.options)
        self._attr_entity_category = entity_category
        self._attr_current_option = enum_options.default
        self._is_gateway_config = is_gateway_config
        if is_gateway_config:
            self._track_gateway_availability = False
            self._attr_available = True

    async def async_added_to_hass(self) -> None:
        """Restore last selected option on restart."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state in self._attr_options:
                self._attr_current_option = last_state.state
        if self._attr_current_option is not None:
            self._set_config(self._attr_current_option)

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        self._attr_current_option = option
        self._set_config(option)
        self.async_write_ha_state()

    def _set_config(self, value: str) -> None:
        if self._is_gateway_config:
            self.gateway.set_gateway_config(self.entity_key, value)
        else:
            self.gateway.set_device_config(self.address, self.entity_key, value)


class _SenderSlotSelectBase(EnOceanEntity, SelectEntity):
    """Shared base for sender-slot selects that show dynamic address/device labels."""

    def __init__(
        self,
        address: EURID,
        entity_key: str,
        gateway: Gateway,
        entity_category: EntityCategory | None,
    ) -> None:
        super().__init__(address, entity_key, gateway)
        self._attr_entity_category = entity_category
        self._track_gateway_availability = False
        self._attr_available = True
        self._label_to_key: dict[str, str] = {}
        self._attr_options: list[str] = []

    # ------------------------------------------------------------------
    # Option building
    # ------------------------------------------------------------------

    @staticmethod
    def _build_label(
        slot_key: str, address: SenderAddress | None, device_names: list[str]
    ) -> str:
        if slot_key == "auto":
            return "Auto"
        assert address is not None
        if not device_names:
            return f"{address} —"
        if len(device_names) == 1:
            return f"{address} ({device_names[0]})"
        return f"{address} ({device_names[0]} [+{len(device_names) - 1}])"

    def _device_name(self, eurid: EURID) -> str:
        registry = dr.async_get(self.hass)
        entry = registry.async_get_device(identifiers={(DOMAIN, str(eurid))})
        if entry is not None:
            return entry.name_by_user or entry.name or str(eurid)
        return str(eurid)

    def _options_from(
        self,
        raw: list[tuple[str, SenderAddress | None, list[EURID]]],
        current_key: str,
    ) -> None:
        labels: list[str] = []
        label_to_key: dict[str, str] = {}
        for slot_key, address, devices in raw:
            device_names = [self._device_name(e) for e in devices]
            label = self._build_label(slot_key, address, device_names)
            label_to_key[label] = slot_key
            labels.append(label)
        self._label_to_key = label_to_key
        self._attr_options = labels
        self._attr_current_option = next(
            (label for label, key in label_to_key.items() if key == current_key),
            labels[0] if labels else None,
        )

    def _refresh_options(self) -> None:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # HA lifecycle
    # ------------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        """Refresh options once hass and the device registry are available."""
        await super().async_added_to_hass()
        self._refresh_options()

    def _update_from_observation(self, _observation: Observation) -> None:
        """Refresh options when an observation arrives for this entity."""
        self._refresh_options()
        self.async_write_ha_state()


class EnOceanLearningSenderSelect(_SenderSlotSelectBase):
    """Dynamic select for the gateway-level learning sender slot."""

    def _refresh_options(self) -> None:
        current_key = self.gateway.config.get(self.entity_key, "auto")
        self._options_from(self.gateway.learning_sender_options(), current_key)

    async def async_select_option(self, option: str) -> None:
        """Persist the selected sender slot key to gateway config."""
        key = self._label_to_key.get(option, "auto")
        self._attr_current_option = option
        self.gateway.set_gateway_config(self.entity_key, key)
        self.async_write_ha_state()


class EnOceanDeviceSenderSlotSelect(_SenderSlotSelectBase):
    """Dynamic select for a device's assigned sender slot."""

    @staticmethod
    def _build_label(
        slot_key: str, address: SenderAddress | None, device_names: list[str]
    ) -> str:
        if slot_key == "auto":
            return "Auto"
        assert address is not None
        return str(address)

    def _refresh_options(self) -> None:
        raw = self.gateway.learning_sender_options(for_device=self.address)
        # The device's currently-assigned slot is the one where self.address appears
        # in the devices list.  Fall back to "auto" if not found (unassigned).
        current_key = next(
            (slot_key for slot_key, _, devices in raw if self.address in devices),
            "auto",
        )
        self._options_from(raw, current_key)

    async def async_select_option(self, option: str) -> None:
        """Persist the selected sender slot key to device config."""
        key = self._label_to_key.get(option, "auto")
        self._attr_current_option = option
        self.gateway.set_device_config(self.address, self.entity_key, key)
        self.async_write_ha_state()
