"""Eventlet util methods."""


def spawn(hub, func, *args, **kwargs):
    """Spawns a function on specified hub."""
    import eventlet
    g = eventlet.greenthread.GreenThread(hub.greenlet)
    hub.schedule_call_global(0, g.switch, func, args, kwargs)
    return g
