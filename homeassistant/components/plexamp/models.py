""" Models for the Plexamp integration."""


class BaseMediaPlayerFactory:
    """Factory for creating a base media player (before actually creating the device in HA"""

    name: str
    product: str
    product_version: str
    client_identifier: str
    protocol: str
    address: str
    port: str
    uri: str
    server_uri: str

    def __init__(
        self,
        name: str,
        product: str,
        product_version: str,
        client_identifier: str,
        protocol: str,
        address: str,
        port: str,
        uri: str,
        server: dict,
    ) -> None:
        self.name = name
        self.product = product
        self.product_version = product_version
        self.client_identifier = client_identifier
        self.protocol = protocol
        self.address = address
        self.port = port
        self.uri = uri
        self.server = server

    def to_dict(self) -> dict:
        """Return a dictionary representation of the instance's data attributes."""
        return {
            "name": self.name,
            "product": self.product,
            "product_version": self.product_version,
            "client_identifier": self.client_identifier,
            "protocol": self.protocol,
            "address": self.address,
            "port": self.port,
            "uri": self.uri,
            "server": self.server,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BaseMediaPlayerFactory":
        """Create an instance of BaseMediaPlayerFactory from a dictionary."""
        return cls(
            name=data.get("name", ""),
            product=data.get("product", ""),
            product_version=data.get("product_version", ""),
            client_identifier=data.get("client_identifier", ""),
            protocol=data.get("protocol", ""),
            address=data.get("address", ""),
            port=data.get("port", ""),
            uri=data.get("uri", ""),
            server=data.get("server", {}),
        )
