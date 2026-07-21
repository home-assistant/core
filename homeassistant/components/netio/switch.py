"""The Netio switch component."""

from collections import namedtuple
from datetime import timedelta
import logging
from typing import Any, override

from pynetio import Netio
import voluptuous as vol

from homeassistant import util
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.switch import (
    PLATFORM_SCHEMA as SWITCH_PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NetioConfigEntry, NetioDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

ATTR_START_DATE = "start_date"
ATTR_TOTAL_CONSUMPTION_KWH = "total_energy_kwh"

CONF_OUTLETS = "outlets"

DEFAULT_PORT = 1234
DEFAULT_USERNAME = "admin"
Device = namedtuple("Device", ["netio", "entities"])  # noqa: PYI024
DEVICES: dict[str, Device] = {}

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

REQ_CONF = [CONF_HOST, CONF_OUTLETS]

URL_API_NETIO_EP = "/api/netio/{host}"

PLATFORM_SCHEMA = SWITCH_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_OUTLETS): {cv.string: cv.string},
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NetioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Netio switches from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        NetioOutputSwitch(coordinator, output_id) for output_id in coordinator.data
    )


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Netio platform."""

    ir.create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2027.2.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "url": f"/config/integrations/dashboard/add?domain={DOMAIN}",
        },
    )

    host = config[CONF_HOST]
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    port = config[CONF_PORT]

    if not DEVICES:
        hass.http.register_view(NetioApiView)

    dev = Netio(host, port, username, password)

    DEVICES[host] = Device(dev, [])

    # Throttle the update for all Netio switches of one Netio
    dev.update = util.Throttle(MIN_TIME_BETWEEN_SCANS)(dev.update)

    for key in config[CONF_OUTLETS]:
        switch = NetioSwitch(DEVICES[host].netio, key, config[CONF_OUTLETS][key])
        DEVICES[host].entities.append(switch)

    add_entities(DEVICES[host].entities)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, dispose)


def dispose(event):
    """Close connections to Netio Devices."""
    for value in DEVICES.values():
        value.netio.stop()


class NetioApiView(HomeAssistantView):
    """WSGI handler class."""

    url = URL_API_NETIO_EP
    name = "api:netio"

    @callback
    def get(self, request, host):
        """Request handler."""
        data = request.query
        states, consumptions, cumulated_consumptions, start_dates = [], [], [], []

        for i in range(1, 5):
            out = f"output{i}"
            states.append(data.get(f"{out}_state") == STATE_ON)
            consumptions.append(float(data.get(f"{out}_consumption", 0)))
            cumulated_consumptions.append(
                float(data.get(f"{out}_cumulatedConsumption", 0)) / 1000
            )
            start_dates.append(data.get(f"{out}_consumptionStart", ""))

        _LOGGER.debug(
            "%s: %s, %s, %s since %s",
            host,
            states,
            consumptions,
            cumulated_consumptions,
            start_dates,
        )

        ndev = DEVICES[host].netio
        ndev.consumptions = consumptions
        ndev.cumulated_consumptions = cumulated_consumptions
        ndev.states = states
        ndev.start_dates = start_dates

        for dev in DEVICES[host].entities:
            dev.async_write_ha_state()

        return self.json(True)


class NetioOutputSwitch(CoordinatorEntity[NetioDataUpdateCoordinator], SwitchEntity):
    """Switch for a single output of a Netio device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NetioDataUpdateCoordinator, output_id: int) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._output_id = output_id
        self._attr_unique_id = f"{coordinator.device.SerialNumber}_{output_id}"
        self._attr_device_info = coordinator.device_info

    @property
    @override
    def available(self) -> bool:
        """Return True if the output is present in coordinator data."""
        return super().available and self._output_id in self.coordinator.data

    @property
    @override
    def name(self) -> str:
        """Return the output name configured on the device."""
        output = self.coordinator.data.get(self._output_id)
        if output is None or not output.Name:
            return f"Output {self._output_id}"
        return output.Name

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if the output is on."""
        if (output := self.coordinator.data.get(self._output_id)) is None:
            return None
        return output.State == 1

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the output on."""
        await self.coordinator.async_set_output(self._output_id, True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the output off."""
        await self.coordinator.async_set_output(self._output_id, False)


# Deprecated YAML entity without unique ID, pending removal
# pylint: disable-next=home-assistant-missing-entity-unique-id,home-assistant-missing-has-entity-name
class NetioSwitch(SwitchEntity):
    """Provide a Netio linked switch."""

    def __init__(self, netio, outlet, name) -> None:
        """Initialize the Netio switch."""
        self._name = name
        self.outlet = outlet
        self.netio = netio

    @property
    @override
    def name(self) -> str:
        """Return the device's name."""
        return self._name

    @property
    @override
    def available(self) -> bool:
        """Return true if entity is available."""
        return not hasattr(self, "telnet")

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Turn switch on."""
        self._set(True)

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Turn switch off."""
        self._set(False)

    def _set(self, value):
        val = list("uuuu")
        val[int(self.outlet) - 1] = "1" if value else "0"
        val = "".join(val)
        self.netio.get(f"port list {val}")
        self.netio.states[int(self.outlet) - 1] = value
        self.schedule_update_ha_state()

    @property
    @override
    def is_on(self) -> bool:
        """Return the switch's status."""
        return self.netio.states[int(self.outlet) - 1]

    def update(self) -> None:
        """Update the state."""
        self.netio.update()
