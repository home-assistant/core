---
title: "Working with Async"
---

Although we have a backwards compatible API, using the async core directly will be a lot faster. Most core components have already been rewritten to leverage the async core. This includes the EntityComponent helper (foundation of light, switch, etc), scripts, groups and automation.

## Interacting with the core

All methods in the Home Assistant core are implemented in two flavors: an async version and a version to be called from other threads. The versions for other are merely wrappers that call the async version in a threadsafe manner.

So if you are making calls to the core (the hass object) from within a callback or coroutine, use the methods that start with async_. If you need to call an async_ function that is a coroutine, your task must also be a coroutine.

## Implementing an async component

To make a component async, implement an async_setup.

```python
def setup(hass, config):
    """Set up component."""
    # Code for setting up your component outside of the event loop.
```

Will turn into:

```python
async def async_setup(hass, config):
    """Set up component."""
    # Code for setting up your component inside of the event loop.
```

## Implementing an async platform

For platforms we support async setup. Instead of setup_platform you need to have a coroutine async_setup_platform.

```python
def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up platform."""
    # Code for setting up your platform outside of the event loop.
```

Will turn into:

```python
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up platform."""
    # Code for setting up your platform inside of the event loop.
```

The only difference with the original parameters is that the `add_entities` function has been replaced by the async friendly callback `async_add_entities`.

## Implementing an async entity

You can make your entity async friendly by converting your update method to be async. This requires the dependency of your entities to also be async friendly!

```python
class MyEntity(Entity):
    def update(self):
        """Retrieve latest state."""
        self._state = fetch_state()
```

Will turn into:

```python
class MyEntity(Entity):
    async def async_update(self):
        """Retrieve latest state."""
        self._state = await async_fetch_state()
```

Make sure that all properties defined on your entity do not result in I/O being done. All data has to be fetched inside the update method and cached on the entity. This is because these properties are read from within the event loop and thus doing I/O will result in the core of Home Assistant waiting until your I/O is done.

## Calling async functions from threads

Sometimes it will happen that you’re in a thread and you want to call a function that is only available as async. Home Assistant includes a few async helper utilities to help with this.

In the following example, `say_hello` will schedule `async_say_hello` and block till the function has run and get the result back.

```python
import asyncio


def say_hello(hass, target):
    return asyncio.run_coroutine_threadsafe(
        async_say_hello(hass, target), hass.loop
    ).result()


async def async_say_hello(hass, target):
    return f"Hello {target}!"
```

**Warning:** be careful with this! If the async function uses executor jobs, it can lead to a deadlock.

## Calling sync functions from async

If you are running inside an async context, it might sometimes be necessary to call a sync function. Do this like this:

```python
# hub.update() is a sync function.
result = await hass.async_add_executor_job(hub.update)
```

## Starting independent task from async

If you want to spawn a task that will not block the current async context, you can choose to create it as a task on the event loop. It will then be executed in parallel.

```python
hass.async_create_task(async_say_hello(hass, target))
```
