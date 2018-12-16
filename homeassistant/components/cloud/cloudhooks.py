"""Manage cloud cloudhooks."""
import async_timeout

from . import cloud_api


class Cloudhooks:
    """Class to help manage cloudhooks."""

    def __init__(self, cloud):
        """Initialize cloudhooks."""
        self.cloud = cloud
        self.cloud.iot.register_on_connect(self.async_publish_cloudhooks)

    async def async_publish_cloudhooks(self):
        """Inform the Relayer of the cloudhooks that we support."""
        cloudhooks = self.cloud.prefs.cloudhooks
        await self.cloud.iot.async_send_message('webhook-register', {
            'cloudhook_ids': [info['cloudhook_id'] for info
                              in cloudhooks.values()]
        }, expect_answer=False)

    async def async_create(self, webhook_id):
        """Create a cloud webhook."""
        cloudhooks = self.cloud.prefs.cloudhooks

        if webhook_id in cloudhooks:
            raise ValueError('Hook is already enabled for the cloud.')

        if not self.cloud.iot.connected:
            raise ValueError("Cloud is not connected")

        # Create cloud hook
        with async_timeout.timeout(10):
            resp = await cloud_api.async_create_cloudhook(self.cloud)

        data = await resp.json()
        cloudhook_id = data['cloudhook_id']
        cloudhook_url = data['url']

        # Store hook
        cloudhooks = dict(cloudhooks)
        hook = cloudhooks[webhook_id] = {
            'webhook_id': webhook_id,
            'cloudhook_id': cloudhook_id,
            'cloudhook_url': cloudhook_url
        }
        await self.cloud.prefs.async_update(cloudhooks=cloudhooks)

        await self.async_publish_cloudhooks()

        return hook

    async def async_delete(self, webhook_id):
        """Delete a cloud webhook."""
        cloudhooks = self.cloud.prefs.cloudhooks

        if webhook_id not in cloudhooks:
            raise ValueError('Hook is not enabled for the cloud.')

        # Remove hook
        cloudhooks = dict(cloudhooks)
        cloudhooks.pop(webhook_id)
        await self.cloud.prefs.async_update(cloudhooks=cloudhooks)

        await self.async_publish_cloudhooks()
