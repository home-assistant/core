""" Models for the Plexamp integration."""


class BaseMediaPlayerFactory:
    """ Factory for creating a base media player (before actually creating the device in HA"""
    name: str
    host: str
    identifier: str
    ip: str

    def __init__(self, name: str, host: str, identifier: str, ip: str) -> None:
        self.name = name
        self.host = host
        self.identifier = identifier
        self.ip = ip

    def to_dict(self) -> dict:
        """Return a dictionary representation of the instance's data attributes."""
        return {
            'name': self.name,
            'host': self.host,
            'identifier': self.identifier,
            'ip': self.ip
        }