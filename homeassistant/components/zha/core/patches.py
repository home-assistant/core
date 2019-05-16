"""
Patch functions for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""


def apply_application_controller_patch(zha_gateway):
    """Apply patches to ZHA objects."""
    # Patch handle_message until zigpy can provide an event here
    def handle_message(sender, is_reply, profile, cluster,
                       src_ep, dst_ep, tsn, command_id, args):
        """Handle message from a device."""
        if not sender.initializing and sender.ieee in zha_gateway.devices and \
                not zha_gateway.devices[sender.ieee].available:
            zha_gateway.async_device_became_available(
                sender, is_reply, profile, cluster, src_ep, dst_ep, tsn,
                command_id, args
            )
        return sender.handle_message(
            is_reply, profile, cluster, src_ep, dst_ep, tsn, command_id, args)

    zha_gateway.application_controller.handle_message = handle_message
