"""Update for Olarm Integration."""
# pylint: disable=hass-component-root-import, deprecated-module
from distutils.dir_util import copy_tree
import os
import subprocess
from typing import Any

from homeassistant.components.update import UpdateEntity, const
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, VERSION

PATH = os.path.abspath(__file__).replace("update.py", "")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Update entities."""
    for device in hass.data[DOMAIN]["devices"]:
        async_add_entities([OlarmUpdate(hass, device)])


class OlarmUpdate(UpdateEntity):
    """Update entity."""

    _attr_installed_version = VERSION
    _attr_supported_features = const.UpdateEntityFeature(1) | const.UpdateEntityFeature(
        8
    )

    def __init__(self, hass: HomeAssistant, device) -> None:
        """Initiate update thingy."""
        self.hass = hass
        self.device = device

    @property
    def name(self) -> str:
        """Return sensor name."""
        return "Olarm Sensors Update"

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        return self.hass.data[DOMAIN]["release_data"]["name"].split(" ")[1]

    @property
    def title(self) -> str | None:
        """Return update name."""
        return self.hass.data[DOMAIN]["release_data"]["name"]

    @property
    def release_summary(self) -> str | None:
        """Return release summary."""
        return self.hass.data[DOMAIN]["release_data"]["body"].split("\n", maxsplit=1)[0]

    @property
    def release_url(self) -> str | None:
        """The url of the release."""
        return self.hass.data[DOMAIN]["release_data"]["url"]

    def install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
        """Install an update.

        Version can be specified to install a specific version. When `None`, the
        latest version needs to be installed.

        The backup parameter indicates a backup should be taken before
        installing the update.
        """
        github_repository = "https://github.com/rainepretorius/olarm-ha-integration"

        subprocess.run(
            [
                "git",
                "clone",
                github_repository,
                os.path.join(PATH, "download"),
            ],
            check=False,
        )
        copy_tree(
            str(os.path.join(PATH, "download", "custom_components", "olarm_sensors")),
            str(os.path.join(PATH, "test")),
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            name=f"Olarm Sensors ({self.device['deviceName']})",
            manufacturer="Raine Pretorius",
            model=self.device["deviceAlarmType"],
            identifiers={(DOMAIN, self.device["deviceId"])},
            sw_version=VERSION,
            hw_version=self.device["device_firmware"],
        )

    def release_notes(self) -> str | None:
        """Return the release notes."""
        return self.hass.data[DOMAIN]["release_data"]["html_url"]
