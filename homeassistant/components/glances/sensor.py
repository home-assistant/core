"""Support gathering system information of hosts which are running glances."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME, STATE_UNAVAILABLE
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_UPDATED, DOMAIN, SENSOR_TYPES, GlancesSensorEntityDescription


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Glances sensors."""

    client = hass.data[DOMAIN][config_entry.entry_id]
    name = config_entry.data[CONF_NAME]
    dev = []

    for description in SENSOR_TYPES:
        if description.type == "fs":
            # fs will provide a list of disks attached
            for disk in client.api.data[description.type]:
                dev.append(
                    GlancesSensor(
                        client,
                        name,
                        disk["mnt_point"],
                        description,
                    )
                )
        elif description.type == "sensors":
            # sensors will provide temp for different devices
            for sensor in client.api.data[description.type]:
                if sensor["type"] == description.key:
                    dev.append(
                        GlancesSensor(
                            client,
                            name,
                            sensor["label"],
                            description,
                        )
                    )
        elif client.api.data[description.type]:
            dev.append(
                GlancesSensor(
                    client,
                    name,
                    "",
                    description,
                )
            )

    async_add_entities(dev, True)


class GlancesSensor(SensorEntity):
    """Implementation of a Glances sensor."""

    entity_description: GlancesSensorEntityDescription

    def __init__(
        self,
        glances_data,
        name,
        sensor_name_prefix,
        description: GlancesSensorEntityDescription,
    ):
        """Initialize the sensor."""
        self.glances_data = glances_data
        self._sensor_name_prefix = sensor_name_prefix
        self._state = None
        self.unsub_update = None

        self.entity_description = description
        self._attr_name = f"{name} {sensor_name_prefix} {description.name_suffix}"

    @property
    def unique_id(self):
        """Set unique_id for sensor."""
        return f"{self.glances_data.host}-{self.name}"

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self.glances_data.available

    @property
    def state(self):
        """Return the state of the resources."""
        return self._state

    @property
    def should_poll(self):
        """Return the polling requirement for this sensor."""
        return False

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        self.unsub_update = async_dispatcher_connect(
            self.hass, DATA_UPDATED, self._schedule_immediate_update
        )

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)

    async def will_remove_from_hass(self):
        """Unsubscribe from update dispatcher."""
        if self.unsub_update:
            self.unsub_update()
        self.unsub_update = None

    async def async_update(self):  # noqa: C901
        """Get the latest data from REST API."""
        value = self.glances_data.api.data
        if value is None:
            return

        if self.entity_description.type == "fs":
            for var in value["fs"]:
                if var["mnt_point"] == self._sensor_name_prefix:
                    disk = var
                    break
            if self.entity_description.key == "disk_free":
                try:
                    self._state = round(disk["free"] / 1024 ** 3, 1)
                except KeyError:
                    self._state = round(
                        (disk["size"] - disk["used"]) / 1024 ** 3,
                        1,
                    )
            elif self.entity_description.key == "disk_use":
                self._state = round(disk["used"] / 1024 ** 3, 1)
            elif self.entity_description.key == "disk_use_percent":
                self._state = disk["percent"]
        elif self.entity_description.key == "battery":
            for sensor in value["sensors"]:
                if (
                    sensor["type"] == "battery"
                    and sensor["label"] == self._sensor_name_prefix
                ):
                    self._state = sensor["value"]
        elif self.entity_description.key == "fan_speed":
            for sensor in value["sensors"]:
                if (
                    sensor["type"] == "fan_speed"
                    and sensor["label"] == self._sensor_name_prefix
                ):
                    self._state = sensor["value"]
        elif self.entity_description.key == "temperature_core":
            for sensor in value["sensors"]:
                if (
                    sensor["type"] == "temperature_core"
                    and sensor["label"] == self._sensor_name_prefix
                ):
                    self._state = sensor["value"]
        elif self.entity_description.key == "temperature_hdd":
            for sensor in value["sensors"]:
                if (
                    sensor["type"] == "temperature_hdd"
                    and sensor["label"] == self._sensor_name_prefix
                ):
                    self._state = sensor["value"]
        elif self.entity_description.key == "memory_use_percent":
            self._state = value["mem"]["percent"]
        elif self.entity_description.key == "memory_use":
            self._state = round(value["mem"]["used"] / 1024 ** 2, 1)
        elif self.entity_description.key == "memory_free":
            self._state = round(value["mem"]["free"] / 1024 ** 2, 1)
        elif self.entity_description.key == "swap_use_percent":
            self._state = value["memswap"]["percent"]
        elif self.entity_description.key == "swap_use":
            self._state = round(value["memswap"]["used"] / 1024 ** 3, 1)
        elif self.entity_description.key == "swap_free":
            self._state = round(value["memswap"]["free"] / 1024 ** 3, 1)
        elif self.entity_description.key == "processor_load":
            # Windows systems don't provide load details
            try:
                self._state = value["load"]["min15"]
            except KeyError:
                self._state = value["cpu"]["total"]
        elif self.entity_description.key == "process_running":
            self._state = value["processcount"]["running"]
        elif self.entity_description.key == "process_total":
            self._state = value["processcount"]["total"]
        elif self.entity_description.key == "process_thread":
            self._state = value["processcount"]["thread"]
        elif self.entity_description.key == "process_sleeping":
            self._state = value["processcount"]["sleeping"]
        elif self.entity_description.key == "cpu_use_percent":
            self._state = value["quicklook"]["cpu"]
        elif self.entity_description.key == "docker_active":
            count = 0
            try:
                for container in value["docker"]["containers"]:
                    if container["Status"] == "running" or "Up" in container["Status"]:
                        count += 1
                self._state = count
            except KeyError:
                self._state = count
        elif self.entity_description.key == "docker_cpu_use":
            cpu_use = 0.0
            try:
                for container in value["docker"]["containers"]:
                    if container["Status"] == "running" or "Up" in container["Status"]:
                        cpu_use += container["cpu"]["total"]
                    self._state = round(cpu_use, 1)
            except KeyError:
                self._state = STATE_UNAVAILABLE
        elif self.entity_description.key == "docker_memory_use":
            mem_use = 0.0
            try:
                for container in value["docker"]["containers"]:
                    if container["Status"] == "running" or "Up" in container["Status"]:
                        mem_use += container["memory"]["usage"]
                    self._state = round(mem_use / 1024 ** 2, 1)
            except KeyError:
                self._state = STATE_UNAVAILABLE
