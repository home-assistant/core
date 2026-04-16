    @property
    def device_info(self):
        info = DeviceInfo(
            identifiers={(DOMAIN, self._device_unique_name)},
            name=self._device_name,
            manufacturer='STIPS',
            model='IRU1',
            connections={(dr.CONNECTION_NETWORK_MAC, self._device_mac)} if self._device_mac else set()
        )
        if device_host:
            info['configuration_url'] = device_host
        return info
