"""
Patch functions for Zigbee Home Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/zha/
"""

import types


def apply_cluster_listener_patch():
    """Apply patches to ZHA objects."""
    # patch zigpy listener to prevent flooding logs with warnings due to
    # how zigpy implemented its listeners
    from zigpy.appdb import ClusterPersistingListener

    def zha_send_event(self, cluster, command, args):
        pass

    ClusterPersistingListener.zha_send_event = types.MethodType(
        zha_send_event,
        ClusterPersistingListener
    )


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
