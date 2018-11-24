"""Manage cloud webhooks."""
import async_timeout

from . import cloud_api


class Webhooks:
    """Class to help manage webhooks."""

    def __init__(self, cloud):
        """Initialize webhooks."""
        self.cloud = cloud
        self.cloud.iot.register_on_connect(self.async_publish_webhooks)

    async def async_publish_webhooks(self):
        """Inform the Relayer of the webhooks that we expect."""
        await self.cloud.iot.async_send_message('webhook-register', {
            'webhook_ids': [info['cloud_id'] for info
                            in self.cloud.prefs.webhooks.values()]
        })

    async def async_enable(self, webhook_id):
        """Enable a webhook."""
        webhooks = self.cloud.prefs.webhooks

        if webhook_id in webhooks:
            raise ValueError('Hook is already enabled for the cloud.')

        if not self.cloud.iot.connected:
            raise ValueError("Cloud is not connected")

        # Create cloud hook
        with async_timeout.timeout(10):
            resp = await cloud_api.async_create_webhook(self.cloud, webhook_id)

        data = await resp.json()
        cloud_id = data['webhook_id']
        cloud_url = data['url']

        # Store hook
        webhooks = dict(webhooks)
        hook = webhooks[webhook_id] = {
            'webhook_id': webhook_id,
            'cloud_id': cloud_id,
            'cloud_url': cloud_url
        }
        await self.cloud.prefs.async_update(webhooks=webhooks)

        await self.async_publish_webhooks()

        return hook

    async def async_disable(self, webhook_id):
        """Disable a webhook."""
        webhooks = self.cloud.prefs.webhooks

        if webhook_id not in webhooks:
            raise ValueError('Hook is not enabled for the cloud.')

        # Remove hook
        webhooks = dict(webhooks)
        webhooks.pop(webhook_id)
        await self.cloud.prefs.async_update(webhooks=webhooks)

        await self.async_publish_webhooks()
