"""Patch functions for Zigbee Home Automation."""


def apply_application_controller_patch(zha_gateway):
    """Apply patches to ZHA objects."""
    # Patch handle_message until zigpy can provide an event here
    def handle_message(sender, profile, cluster, src_ep, dst_ep, message):
        """Handle message from a device."""
        if (
            not sender.initializing
            and sender.ieee in zha_gateway.devices
            and not zha_gateway.devices[sender.ieee].available
        ):
            zha_gateway.async_device_became_available(
                sender, profile, cluster, src_ep, dst_ep, message
            )
        return sender.handle_message(profile, cluster, src_ep, dst_ep, message)

    zha_gateway.application_controller.handle_message = handle_message
