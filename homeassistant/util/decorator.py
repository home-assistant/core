"""Decorator utility functions."""


class Registry(dict):
    """Registry of items."""

    def register(self, name):
        """Return decorator to register item with a specific name."""
        def decorator(func):
            """Register decorated function."""
            self[name] = func
            return func

        return decorator
