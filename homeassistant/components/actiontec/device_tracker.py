"""Support for Actiontec MI424WR (Verizon FIOS) routers."""

from typing import override

import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    ScannerEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ActiontecConfigEntry, ActiontecDataUpdateCoordinator
from .model import Device

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
    }
)


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    _async_see: AsyncSeeCallback,
    _discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Set up the legacy Actiontec device tracker."""
    import_data = {
        CONF_HOST: config[CONF_HOST],
        CONF_USERNAME: config[CONF_USERNAME],
        CONF_PASSWORD: config[CONF_PASSWORD],
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=import_data
    )

    if result["type"] is FlowResultType.ABORT and result["reason"] == "cannot_connect":
        ir.async_create_issue(
            hass,
            DOMAIN,
            "yaml_import_cannot_connect",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.ERROR,
            translation_key="yaml_import_cannot_connect",
            translation_placeholders={"host": import_data[CONF_HOST]},
        )
        return False

    # A previous failed import may have raised this issue; clear it on success.
    ir.async_delete_issue(hass, DOMAIN, "yaml_import_cannot_connect")
    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Actiontec",
        },
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ActiontecConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Actiontec device tracker from a config entry."""
    coordinator = config_entry.runtime_data
    tracked: set[str] = set()

    @callback
    def _async_add_new_devices() -> None:
        """Add newly discovered devices from the coordinator."""
        new_entities: list[ActiontecScannerEntity] = []
        for device in coordinator.data:
            if device.mac_address in tracked:
                continue
            tracked.add(device.mac_address)
            new_entities.append(ActiontecScannerEntity(coordinator, device.mac_address))
        if new_entities:
            async_add_entities(new_entities)

    config_entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))
    _async_add_new_devices()


class ActiontecScannerEntity(
    CoordinatorEntity[ActiontecDataUpdateCoordinator], ScannerEntity
):
    """Representation of a device connected to the Actiontec router."""

    def __init__(
        self, coordinator: ActiontecDataUpdateCoordinator, mac_address: str
    ) -> None:
        """Initialize the tracked device."""
        super().__init__(coordinator)
        self._mac_address = mac_address
        if (device := self._device) is not None:
            self._attr_name = device.ip_address

    @property
    def _device(self) -> Device | None:
        """Return the current device data."""
        return next(
            (
                device
                for device in self.coordinator.data
                if device.mac_address == self._mac_address
            ),
            None,
        )

    @property
    @override
    def is_connected(self) -> bool:
        """Return true if the device is connected to the Actiontec router."""
        return self._device is not None

    @property
    @override
    def ip_address(self) -> str | None:
        """Return the primary IP address of the device."""
        if (device := self._device) is not None:
            return device.ip_address
        return None

    @property
    @override
    def mac_address(self) -> str:
        """Return the MAC address of the device."""
        return self._mac_address
