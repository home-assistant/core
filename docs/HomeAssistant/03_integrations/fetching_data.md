---
title: "Fetching data"
---

Your integration will need to fetch data from an API to be able to provide this to Home Assistant. This API can be available over the web (local or cloud), sockets, serial ports exposed via USB sticks, etc.

## Push vs poll

APIs come in many different shapes and forms but at its core they fall in two categories: push and poll.

With push, we subscribe to an API and we get notified by the API when new data is available. It pushes the changes to us. Push APIs are great because they consume less resources. When a change happens, we can get notified of a change and don't have to re-fetch all the data and find changes. Because entities can be disabled, you should make sure that your entity subscribes inside the `async_added_to_hass` callback and unsubscribes on remove.

With polling, we will fetch the latest data from the API at a specified interval. Your integration will then supply this data to its entity, which is written to Home Assistant.

Because polling is so common, Home Assistant by default assumes that your entity is based on polling. If this is not the case, return `False` from the `Entity.should_poll` property. When you disable polling, your integration will be responsible for calling one of the methods to indicate to Home Assistant that it's time to write the entity state to Home Assistant:

- If you are executing from within an async function and don't need your entity update method called, call `Entity.async_write_ha_state()`. This is an async callback that will write the state to the state machine within yielding to the event loop.
- `Entity.schedule_update_ha_state(force_refresh=False)`/`Entity.async_schedule_update_ha_state(force_refresh=False)` will schedule an update of the entity. If `force_refresh` is set to `True`, Home Assistant will call your entities update method (`update()`/`async_update()`) prior to writing the state.

## Polling API endpoints

We're going to explain a few different API types here and the best way to integrate them in Home Assistant. Note that some integrations will encounter a combination of the ones below.

### Coordinated, single API poll for data for all entities

This API will have a single method to fetch data for all the entities that you have in Home Assistant. In this case we will want to have a single periodical poll on this endpoint, and then let entities know as soon as new data is available for them.

Home Assistant provides a DataUpdateCoordinator class to help you manage this as efficiently as possible.

When using the DataUpdateCoordinator, the data being polled is often expected to stay mostly the same. For example, if you are polling a light that is only turned on once a week, that data may be the same nearly all the time. The default behavior is always calling back listeners when the data is updated, even if it does not change. If the data returned from the API can be compared for changes with the Python `__eq__` method, set `always_update=False` when creating the DataUpdateCoordinator to avoid unnecessary callbacks and writes to the state machine.

```python
"""Example integration using DataUpdateCoordinator."""

from datetime import timedelta
import logging

import async_timeout

from homeassistant.components.light import LightEntity
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Config entry example."""
    # assuming API object stored here by __init__.py
    my_api = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = MyCoordinator(hass, config_entry, my_api)

    # Fetch initial data so we have data when entities subscribe
    #
    # If the refresh fails, async_config_entry_first_refresh will
    # raise ConfigEntryNotReady and setup will try again later
    #
    # If you do not want to retry setup on failure, use
    # coordinator.async_refresh() instead
    #
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        MyEntity(coordinator, idx) for idx, ent in enumerate(coordinator.data)
    )


class MyCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(self, hass, config_entry, my_api):
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="My sensor",
            config_entry=config_entry,
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=30),
            # Set always_update to `False` if the data returned from the
            # api can be compared via `__eq__` to avoid duplicate updates
            # being dispatched to listeners
            always_update=True
        )
        self.my_api = my_api
        self._device: MyDevice | None = None

    async def _async_setup(self):
        """Set up the coordinator

        This is the place to set up your coordinator,
        or to load data, that only needs to be loaded once.

        This method will be called automatically during
        coordinator.async_config_entry_first_refresh.
        """
        self._device = await self.my_api.get_device()

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                # Grab active context variables to limit data required to be fetched from API
                # Note: using context is not required if there is no need or ability to limit
                # data retrieved from API.
                listening_idx = set(self.async_contexts())
                return await self.my_api.fetch_data(listening_idx)
        except ApiAuthError as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            raise ConfigEntryAuthFailed from err
        except ApiError as err:
            raise UpdateFailed(f"Error communicating with API: {err}")
        except ApiRateLimited as err:
            # If the API is providing backoff signals, these can be honored via the retry_after parameter
            raise UpdateFailed(retry_after=60)


class MyEntity(CoordinatorEntity, LightEntity):
    """An entity using CoordinatorEntity.

    The CoordinatorEntity class provides:
      should_poll
      async_update
      async_added_to_hass
      available

    """

    def __init__(self, coordinator, idx):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, context=idx)
        self.idx = idx

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self.coordinator.data[self.idx]["state"]
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        """Turn the light on.

        Example method how to request data updates.
        """
        # Do the turning on.
        # ...

        # Update the data
        await self.coordinator.async_request_refresh()
```

### Separate polling for each individual entity

Some APIs will offer an endpoint per device. It sometimes won't be possible to map a device from your API to a single entity. If you create multiple entities from a single API device endpoint, please see the previous section.

If you can map exactly one device endpoint to a single entity, you can fetch the data for this entity inside the `update()`/`async_update()` methods. Make sure polling is set to `True` and Home Assistant will call this method regularly.

If your entities need to fetch data before being written to Home Assistant for the first time, pass `update_before_add=True` to the `add_entities` method: `add_entities([MyEntity()], update_before_add=True)`.

You can control the polling interval for your integration by defining a `SCAN_INTERVAL` constant in your platform. Careful with setting this too low. It will take up resources in Home Assistant, can overwhelm the device hosting the API or can get you blocked from cloud APIs. The minimum allowed value is 5 seconds.

```python
from datetime import timedelta

SCAN_INTERVAL = timedelta(seconds=5)
```

## Pushing API endpoints

If you have an API endpoint that pushes data, you can still use the data update coordinator if you want. Do this by not passing polling parameters `update_method` and `update_interval` to the constructor.

When new data arrives, use `coordinator.async_set_updated_data(data)` to pass the data to the entities. If this method is used on a coordinator that polls, it will reset the time until the next time it will poll for data.

## Request parallelism

:::info
This is an advanced topic.
:::

Home Assistant has built-in logic to make sure that integrations do not hammer APIs and consume all available resources in Home Assistant. This logic is built around limiting the number of parallel requests. This logic is automatically used during service action calls and entity updates.

Home Assistant controls the number of parallel updates (calls to `update()`) by maintaining a [semaphore](https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore) per integration. For example, if the semaphore allows 1 parallel connection, updates and service action calls will wait if one is in progress. If the value is 0, the integration is itself responsible for limiting the number of parallel requests if necessary.

The default value for parallel requests for a platform is decided based on the first entity that is added to Home Assistant. It's 0 if the entity defines the `async_update` method, else it's 1. (this is a legacy decision)

Platforms can override the default by defining the `PARALLEL_UPDATES` constant in their platform (ie `rflink/light.py`).
