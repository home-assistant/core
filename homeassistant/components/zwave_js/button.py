"""Representation of Z-Wave buttons."""

from typing import override

from zwave_js_server.const import CommandClass
from zwave_js_server.const.command_class.notification import (
    CC_SPECIFIC_NOTIFICATION_TYPE,
    NotificationType,
)
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.node import Node as ZwaveNode

from homeassistant.components.button import (
    DOMAIN as BUTTON_DOMAIN,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import NewZwaveDiscoveryInfo, ZWaveBaseEntity, ZWaveNodeBaseEntity
from .models import (
    NewZWaveDiscoverySchema,
    ValueType,
    ZwaveDiscoveryInfo,
    ZwaveJSConfigEntry,
    ZWaveValueDiscoverySchema,
)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ZwaveJSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Z-Wave button from config entry."""
    client = config_entry.runtime_data.client

    @callback
    def async_add_button(info: ZwaveDiscoveryInfo | NewZwaveDiscoveryInfo) -> None:
        """Add Z-Wave Button."""
        driver = client.driver
        assert driver is not None  # Driver is ready before platforms are loaded.
        entities: list[ZWaveBaseEntity] = []
        if isinstance(info, NewZwaveDiscoveryInfo):
            entities.append(info.entity_class(config_entry, driver, info))
        elif info.platform_hint == "notification idle":
            entities.append(ZWaveNotificationIdleButton(config_entry, driver, info))
        else:
            entities.append(ZwaveBooleanNodeButton(config_entry, driver, info))

        async_add_entities(entities)

    @callback
    def async_add_ping_button_entity(node: ZwaveNode) -> None:
        """Add ping button entity."""
        driver = client.driver
        assert driver is not None  # Driver is ready before platforms are loaded.
        async_add_entities([ZWaveNodePingButton(driver, node)])

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_ping_button_entity",
            async_add_ping_button_entity,
        )
    )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{BUTTON_DOMAIN}",
            async_add_button,
        )
    )


class ZwaveBooleanNodeButton(ZWaveBaseEntity, ButtonEntity):
    """Representation of a ZWave button entity for a boolean value."""

    def __init__(
        self, config_entry: ZwaveJSConfigEntry, driver: Driver, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize entity."""
        super().__init__(config_entry, driver, info)
        self._attr_name = self.generate_name(include_value_name=True)

    @override
    async def async_press(self) -> None:
        """Press the button."""
        await self._async_set_value(self.info.primary_value, True)


class ZWaveNodePingButton(ZWaveNodeBaseEntity, ButtonEntity):
    """Representation of a ping button entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "ping"

    def __init__(self, driver: Driver, node: ZwaveNode) -> None:
        """Initialize a ping Z-Wave device button entity."""
        super().__init__(driver, node)
        self._attr_unique_id = f"{self._base_unique_id}.ping"

    @override
    async def async_press(self) -> None:
        """Press the button."""
        self.hass.async_create_task(self.node.async_ping())


class ZWaveNotificationIdleButton(ZWaveBaseEntity, ButtonEntity):
    """Button to idle Notification CC values."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        config_entry: ZwaveJSConfigEntry,
        driver: Driver,
        info: ZwaveDiscoveryInfo | NewZwaveDiscoveryInfo,
    ) -> None:
        """Initialize a ZWaveNotificationIdleButton entity."""
        super().__init__(config_entry, driver, info)
        if isinstance(info, NewZwaveDiscoveryInfo):
            # Name from the discovery schema, e.g. "Idle Vibration".
            self._attr_name = self.generate_name(name_prefix="Idle")
        else:
            self._attr_name = self.generate_name(
                alternate_value_name=self.info.primary_value.property_name,
                additional_info=[self.info.primary_value.property_key_name],
                name_prefix="Idle",
            )
        self._attr_unique_id = f"{self._attr_unique_id}.notification_idle"

    @override
    async def async_press(self) -> None:
        """Press the button."""
        await self.info.node.async_manually_idle_notification_value(
            self.info.primary_value
        )


DISCOVERY_SCHEMAS: list[NewZWaveDiscoverySchema] = [
    # Zooz ZSE43 Tilt/Shock Sensor. Its Home Security "Cover status" notification
    # is exposed as a vibration binary sensor, so match that idle button here to
    # name it after the sensor and keep it discovered.
    NewZWaveDiscoverySchema(
        platform=Platform.BUTTON,
        manufacturer_id={0x027A},
        product_id={0xE003},
        product_type={0x7000},
        primary_value=ZWaveValueDiscoverySchema(
            command_class={CommandClass.NOTIFICATION},
            property={"Home Security"},
            property_key={"Cover status"},
            type={ValueType.NUMBER},
            any_available_states={(0, "idle")},
            any_available_cc_specific={
                (CC_SPECIFIC_NOTIFICATION_TYPE, NotificationType.HOME_SECURITY)
            },
        ),
        allow_multi=True,
        entity_description=ButtonEntityDescription(
            key="notification_idle", name="Vibration"
        ),
        entity_class=ZWaveNotificationIdleButton,
    ),
]
