"""Eventlet util methods."""


def spawn(hub, func, *args, **kwargs):
    """Spawn a function on specified hub."""
    import eventlet
    gthread = eventlet.greenthread.GreenThread(hub.greenlet)
    hub.schedule_call_global(0, gthread.switch, func, args, kwargs)
    return gthread
