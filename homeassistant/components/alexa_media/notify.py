"""
Alexa Devices notification service.

SPDX-License-Identifier: Apache-2.0

For more details about this platform, please refer to the documentation at
https://community.home-assistant.io/t/echo-devices-alexa-as-media-player-testers-needed/58639
"""
import asyncio
import json
import logging

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    SERVICE_NOTIFY,
    BaseNotificationService,
)

from . import (
    CONF_EMAIL,
    CONF_QUEUE_DELAY,
    DATA_ALEXAMEDIA,
    DEFAULT_QUEUE_DELAY,
    DOMAIN,
    hide_email,
    hide_serial,
)
from .helpers import retry_async

_LOGGER = logging.getLogger(__name__)


@retry_async(limit=5, delay=2, catch_exceptions=True)
async def async_get_service(hass, config, discovery_info=None):
    # pylint: disable=unused-argument
    """Get the demo notification service."""
    result = False
    for account, account_dict in hass.data[DATA_ALEXAMEDIA]["accounts"].items():
        for key, _ in account_dict["devices"]["media_player"].items():
            if key not in account_dict["entities"]["media_player"]:
                _LOGGER.debug(
                    "%s: Media player %s not loaded yet; delaying load",
                    hide_email(account),
                    hide_serial(key),
                )
                return False
    result = hass.data[DATA_ALEXAMEDIA]["notify_service"] = AlexaNotificationService(
        hass
    )
    return result


async def async_unload_entry(hass, entry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Attempting to unload notify")
    target_account = entry.data[CONF_EMAIL]
    other_accounts = False
    for account, account_dict in hass.data[DATA_ALEXAMEDIA]["accounts"].items():
        if account == target_account:
            if "entities" not in account_dict:
                continue
            for device in account_dict["entities"]["media_player"].values():
                entity_id = device.entity_id.split(".")
                hass.services.async_remove(SERVICE_NOTIFY, f"{DOMAIN}_{entity_id[1]}")
        else:
            other_accounts = True
    if not other_accounts:
        hass.services.async_remove(SERVICE_NOTIFY, f"{DOMAIN}")
        if hass.data[DATA_ALEXAMEDIA].get("notify_service"):
            hass.data[DATA_ALEXAMEDIA].pop("notify_service")
    return True


class AlexaNotificationService(BaseNotificationService):
    """Implement Alexa Media Player notification service."""

    def __init__(self, hass):
        """Initialize the service."""
        self.hass = hass
        self.last_called = True

    def convert(self, names, type_="entities", filter_matches=False):
        """Return a list of converted Alexa devices based on names.

        Names may be matched either by serialNumber, accountName, or
        Homeassistant entity_id and can return any of the above plus entities

        Parameters
        ----------
        names : list(string)
            A list of names to convert
        type_ : string
            The type to return entities, entity_ids, serialnumbers, names
        filter_matches : bool
            Whether non-matching items are removed from the returned list.

        Returns
        -------
        list(string)
            List of home assistant entity_ids

        """
        devices = []
        if isinstance(names, str):
            names = [names]
        for item in names:
            matched = False
            for alexa in self.devices:
                # _LOGGER.debug(
                #     "Testing item: %s against (%s, %s, %s, %s)",
                #     item,
                #     alexa,
                #     alexa.name,
                #     hide_serial(alexa.unique_id),
                #     alexa.entity_id,
                # )
                if item in (
                    alexa,
                    alexa.name,
                    alexa.unique_id,
                    alexa.entity_id,
                    alexa.device_serial_number,
                ):
                    if type_ == "entities":
                        converted = alexa
                    elif type_ == "serialnumbers":
                        converted = alexa.device_serial_number
                    elif type_ == "names":
                        converted = alexa.name
                    elif type_ == "entity_ids":
                        converted = alexa.entity_id
                    devices.append(converted)
                    matched = True
                    # _LOGGER.debug("Converting: %s to (%s): %s", item, type_, converted)
            if not filter_matches and not matched:
                devices.append(item)
        return devices

    @property
    def targets(self):
        """Return a dictionary of Alexa devices."""
        devices = {}
        for email, account_dict in self.hass.data[DATA_ALEXAMEDIA]["accounts"].items():
            if "entities" not in account_dict:
                return devices
            for _, entity in account_dict["entities"]["media_player"].items():
                entity_name = (entity.entity_id).split(".")[1]
                devices[entity_name] = entity.unique_id
                if self.last_called and entity.extra_state_attributes.get(
                    "last_called"
                ):
                    entity_name_last_called = (
                        f"last_called{'_'+ email if entity_name[-1:].isdigit() else ''}"
                    )
                    _LOGGER.debug(
                        "%s: Creating last_called target %s using %s",
                        hide_email(email),
                        entity_name_last_called,
                        entity,
                    )
                    devices[entity_name_last_called] = entity.unique_id
        return devices

    @property
    def devices(self):
        """Return a list of Alexa devices."""
        devices = []
        if (
            "accounts" not in self.hass.data[DATA_ALEXAMEDIA]
            and not self.hass.data[DATA_ALEXAMEDIA]["accounts"].items()
        ):
            return devices
        for _, account_dict in self.hass.data[DATA_ALEXAMEDIA]["accounts"].items():
            devices = devices + list(account_dict["entities"]["media_player"].values())
        return devices

    async def async_send_message(self, message="", **kwargs):
        """Send a message to a Alexa device."""
        _LOGGER.debug("Message: %s, kwargs: %s", message, kwargs)
        _LOGGER.debug("Target type: %s", type(kwargs.get(ATTR_TARGET)))
        kwargs["message"] = message
        targets = kwargs.get(ATTR_TARGET)
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        data = kwargs.get(ATTR_DATA)
        if isinstance(targets, str):
            try:
                targets = json.loads(targets)
            except json.JSONDecodeError:
                _LOGGER.error("Target must be a valid json")
                return
        processed_targets = []
        for target in targets:
            _LOGGER.debug("Processing: %s", target)
            try:
                processed_targets += json.loads(target)
                _LOGGER.debug("Processed Target by json: %s", processed_targets)
            except json.JSONDecodeError:
                if target.find(","):
                    processed_targets += list(
                        map(lambda x: x.strip(), target.split(","))
                    )
                    _LOGGER.debug("Processed Target by string: %s", processed_targets)
        entities = self.convert(processed_targets, type_="entities")
        try:
            entities.extend(self.hass.components.group.expand_entity_ids(entities))
        except ValueError:
            _LOGGER.debug("Invalid Home Assistant entity in %s", entities)
        tasks = []
        for account, account_dict in self.hass.data[DATA_ALEXAMEDIA][
            "accounts"
        ].items():
            for alexa in account_dict["entities"]["media_player"].values():
                if data["type"] == "tts":
                    targets = self.convert(
                        entities, type_="entities", filter_matches=True
                    )
                    # _LOGGER.debug("TTS entities: %s", targets)
                    if alexa in targets and alexa.available:
                        _LOGGER.debug("TTS by %s : %s", alexa, message)
                        tasks.append(
                            alexa.async_send_tts(
                                message,
                                queue_delay=self.hass.data[DATA_ALEXAMEDIA]["accounts"][
                                    account
                                ]["options"].get(CONF_QUEUE_DELAY, DEFAULT_QUEUE_DELAY),
                            )
                        )
                elif data["type"] == "announce":
                    targets = self.convert(
                        entities, type_="serialnumbers", filter_matches=True
                    )
                    # _LOGGER.debug(
                    #     "Announce targets: %s entities: %s",
                    #     list(map(hide_serial, targets)),
                    #     entities,
                    # )
                    if alexa.device_serial_number in targets and alexa.available:
                        _LOGGER.debug(
                            ("%s: Announce by %s to " "targets: %s: %s"),
                            hide_email(account),
                            alexa,
                            list(map(hide_serial, targets)),
                            message,
                        )
                        tasks.append(
                            alexa.async_send_announcement(
                                message,
                                targets=targets,
                                title=title,
                                method=(data["method"] if "method" in data else "all"),
                                queue_delay=self.hass.data[DATA_ALEXAMEDIA]["accounts"][
                                    account
                                ]["options"].get(CONF_QUEUE_DELAY, DEFAULT_QUEUE_DELAY),
                            )
                        )
                        break
                elif data["type"] == "push":
                    targets = self.convert(
                        entities, type_="entities", filter_matches=True
                    )
                    if alexa in targets and alexa.available:
                        _LOGGER.debug("Push by %s: %s %s", alexa, title, message)
                        tasks.append(
                            alexa.async_send_mobilepush(
                                message,
                                title=title,
                                queue_delay=self.hass.data[DATA_ALEXAMEDIA]["accounts"][
                                    account
                                ]["options"].get(CONF_QUEUE_DELAY, DEFAULT_QUEUE_DELAY),
                            )
                        )
                elif data["type"] == "dropin_notification":
                    targets = self.convert(
                        entities, type_="entities", filter_matches=True
                    )
                    if alexa in targets and alexa.available:
                        _LOGGER.debug(
                            "Notification dropin by %s: %s %s", alexa, title, message
                        )
                        tasks.append(
                            alexa.async_send_dropin_notification(
                                message,
                                title=title,
                                queue_delay=self.hass.data[DATA_ALEXAMEDIA]["accounts"][
                                    account
                                ]["options"].get(CONF_QUEUE_DELAY, DEFAULT_QUEUE_DELAY),
                            )
                        )
        await asyncio.gather(*tasks)
