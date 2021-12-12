"""Binary sensor for Shelly."""
from __future__ import annotations

from typing import Final, cast

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OPENING,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PROBLEM,
    DEVICE_CLASS_SMOKE,
    DEVICE_CLASS_UPDATE,
    DEVICE_CLASS_VIBRATION,
    STATE_ON,
    BinarySensorEntity,
)
from homeassistant.components.shelly.const import CONF_SLEEP_PERIOD
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENTITY_CATEGORY_DIAGNOSTIC
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import (
    BlockAttributeDescription,
    RestAttributeDescription,
    RpcAttributeDescription,
    ShellyBlockAttributeEntity,
    ShellyRestAttributeEntity,
    ShellyRpcAttributeEntity,
    ShellySleepingBlockAttributeEntity,
    async_setup_entry_attribute_entities,
    async_setup_entry_rest,
    async_setup_entry_rpc,
)
from .utils import (
    get_device_entry_gen,
    is_block_momentary_input,
    is_rpc_momentary_input,
)

SENSORS: Final = {
    ("device", "overtemp"): BlockAttributeDescription(
        name="Overheating",
        device_class=DEVICE_CLASS_PROBLEM,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    ("device", "overpower"): BlockAttributeDescription(
        name="Overpowering",
        device_class=DEVICE_CLASS_PROBLEM,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    ("light", "overpower"): BlockAttributeDescription(
        name="Overpowering",
        device_class=DEVICE_CLASS_PROBLEM,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    ("relay", "overpower"): BlockAttributeDescription(
        name="Overpowering",
        device_class=DEVICE_CLASS_PROBLEM,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    ("sensor", "dwIsOpened"): BlockAttributeDescription(
        name="Door",
        device_class=DEVICE_CLASS_OPENING,
        available=lambda block: cast(int, block.dwIsOpened) != -1,
    ),
    ("sensor", "flood"): BlockAttributeDescription(
        name="Flood", device_class=DEVICE_CLASS_MOISTURE
    ),
    ("sensor", "gas"): BlockAttributeDescription(
        name="Gas",
        device_class=DEVICE_CLASS_GAS,
        value=lambda value: value in ["mild", "heavy"],
        extra_state_attributes=lambda block: {"detected": block.gas},
    ),
    ("sensor", "smoke"): BlockAttributeDescription(
        name="Smoke", device_class=DEVICE_CLASS_SMOKE
    ),
    ("sensor", "vibration"): BlockAttributeDescription(
        name="Vibration", device_class=DEVICE_CLASS_VIBRATION
    ),
    ("input", "input"): BlockAttributeDescription(
        name="Input",
        device_class=DEVICE_CLASS_POWER,
        default_enabled=False,
        removal_condition=is_block_momentary_input,
    ),
    ("relay", "input"): BlockAttributeDescription(
        name="Input",
        device_class=DEVICE_CLASS_POWER,
        default_enabled=False,
        removal_condition=is_block_momentary_input,
    ),
    ("device", "input"): BlockAttributeDescription(
        name="Input",
        device_class=DEVICE_CLASS_POWER,
        default_enabled=False,
        removal_condition=is_block_momentary_input,
    ),
    ("sensor", "extInput"): BlockAttributeDescription(
        name="External Input",
        device_class=DEVICE_CLASS_POWER,
        default_enabled=False,
    ),
    ("sensor", "motion"): BlockAttributeDescription(
        name="Motion", device_class=DEVICE_CLASS_MOTION
    ),
}

REST_SENSORS: Final = {
    "cloud": RestAttributeDescription(
        name="Cloud",
        value=lambda status, _: status["cloud"]["connected"],
        device_class=DEVICE_CLASS_CONNECTIVITY,
        default_enabled=False,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    "fwupdate": RestAttributeDescription(
        name="Firmware Update",
        device_class=DEVICE_CLASS_UPDATE,
        value=lambda status, _: status["update"]["has_update"],
        default_enabled=False,
        extra_state_attributes=lambda status: {
            "latest_stable_version": status["update"]["new_version"],
            "installed_version": status["update"]["old_version"],
            "beta_version": status["update"].get("beta_version", ""),
        },
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
}

RPC_SENSORS: Final = {
    "input": RpcAttributeDescription(
        key="input",
        sub_key="state",
        name="Input",
        device_class=DEVICE_CLASS_POWER,
        default_enabled=False,
        removal_condition=is_rpc_momentary_input,
    ),
    "cloud": RpcAttributeDescription(
        key="cloud",
        sub_key="connected",
        name="Cloud",
        device_class=DEVICE_CLASS_CONNECTIVITY,
        default_enabled=False,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
    "fwupdate": RpcAttributeDescription(
        key="sys",
        sub_key="available_updates",
        name="Firmware Update",
        device_class=DEVICE_CLASS_UPDATE,
        default_enabled=False,
        extra_state_attributes=lambda status, shelly: {
            "latest_stable_version": status.get("stable", {"version": ""})["version"],
            "installed_version": shelly["ver"],
            "beta_version": status.get("beta", {"version": ""})["version"],
        },
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for device."""
    if get_device_entry_gen(config_entry) == 2:
        return await async_setup_entry_rpc(
            hass, config_entry, async_add_entities, RPC_SENSORS, RpcBinarySensor
        )

    if config_entry.data[CONF_SLEEP_PERIOD]:
        await async_setup_entry_attribute_entities(
            hass,
            config_entry,
            async_add_entities,
            SENSORS,
            BlockSleepingBinarySensor,
        )
    else:
        await async_setup_entry_attribute_entities(
            hass, config_entry, async_add_entities, SENSORS, BlockBinarySensor
        )
        await async_setup_entry_rest(
            hass,
            config_entry,
            async_add_entities,
            REST_SENSORS,
            RestBinarySensor,
        )


class BlockBinarySensor(ShellyBlockAttributeEntity, BinarySensorEntity):
    """Represent a block binary sensor entity."""

    @property
    def is_on(self) -> bool:
        """Return true if sensor state is on."""
        return bool(self.attribute_value)


class RestBinarySensor(ShellyRestAttributeEntity, BinarySensorEntity):
    """Represent a REST binary sensor entity."""

    @property
    def is_on(self) -> bool:
        """Return true if REST sensor state is on."""
        return bool(self.attribute_value)


class RpcBinarySensor(ShellyRpcAttributeEntity, BinarySensorEntity):
    """Represent a RPC binary sensor entity."""

    @property
    def is_on(self) -> bool:
        """Return true if RPC sensor state is on."""
        return bool(self.attribute_value)


class BlockSleepingBinarySensor(ShellySleepingBlockAttributeEntity, BinarySensorEntity):
    """Represent a block sleeping binary sensor."""

    @property
    def is_on(self) -> bool:
        """Return true if sensor state is on."""
        if self.block is not None:
            return bool(self.attribute_value)

        return self.last_state == STATE_ON
