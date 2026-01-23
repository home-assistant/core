---
title: Lock entity
sidebar_label: Lock
---

A lock entity is able to be locked and unlocked. Locking and unlocking can optionally be secured with a user code. Some locks also allow for opening of latches, this may also be secured with a user code. Derive a platform entity from [`homeassistant.components.lock.LockEntity`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/lock/__init__.py).

## Properties

:::tip
Properties should always only return information from memory and not do I/O (like network requests). Implement `update()` or `async_update()` to fetch data.
:::

| Name | Type | Default | Description
| ---- | ---- | ------- | -----------
| changed_by | string | None | Describes what the last change was triggered by.
| code_format | string | None | Regex for code format or None if no code is required.
| is_locked | bool | None | Indication of whether the lock is currently locked. Used to determine `state`.
| is_locking | bool | None | Indication of whether the lock is currently locking. Used to determine `state`.
| is_unlocking | bool | None | Indication of whether the lock is currently unlocking. Used to determine `state`.
| is_jammed | bool | None | Indication of whether the lock is currently jammed. Used to determine `state`.
| is_opening | bool | None | Indication of whether the lock is currently opening. Used to determine `state`.
| is_open | bool | None | Indication of whether the lock is currently open. Used to determine `state`.

### States

The state is defined by setting the above properties. The resulting state is using the `LockState` enum to return one of the below members.

| Value       | Description                                                        |
|-------------|--------------------------------------------------------------------|
| `LOCKED`    | The lock is locked.                                                |
| `LOCKING`   | The lock is locking.                                               |
| `UNLOCKING` | The lock is unlocking.                                             |
| `UNLOCKED`  | The lock is unlocked.                                             |
| `JAMMED`    | The lock is currently jammed.                                      |
| `OPENING`   | The lock is opening.                                               |
| `OPEN`      | The lock is open.                                                  |

## Supported features

Supported features are defined by using values in the `LockEntityFeature` enum
and are combined using the bitwise or (`|`) operator.

| Value  | Description                                |
| ------ | ------------------------------------------ |
| `OPEN` | This lock supports opening the door latch. |

## Methods

### Lock

```python
class MyLock(LockEntity):

    def lock(self, **kwargs):
        """Lock all or specified locks. A code to lock the lock with may optionally be specified."""

    async def async_lock(self, **kwargs):
        """Lock all or specified locks. A code to lock the lock with may optionally be specified."""
```

### Unlock

```python
class MyLock(LockEntity):

    def unlock(self, **kwargs):
        """Unlock all or specified locks. A code to unlock the lock with may optionally be specified."""

    async def async_unlock(self, **kwargs):
        """Unlock all or specified locks. A code to unlock the lock with may optionally be specified."""
```

### Open

Only implement this method if the flag `SUPPORT_OPEN` is set.

```python
class MyLock(LockEntity):

    def open(self, **kwargs):
        """Open (unlatch) all or specified locks. A code to open the lock with may optionally be specified."""

    async def async_open(self, **kwargs):
        """Open (unlatch) all or specified locks. A code to open the lock with may optionally be specified."""
```
