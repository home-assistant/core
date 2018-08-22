"""Helpers to setup multi-factor auth module."""
import logging

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components import websocket_api
from homeassistant.core import callback

WS_TYPE_SETUP_MFA = 'auth/setup_mfa'
SCHEMA_WS_SETUP_MFA = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_SETUP_MFA,
    vol.Exclusive('mfa_module_id', 'module_or_flow_id'): str,
    vol.Exclusive('flow_id', 'module_or_flow_id'): str,
    vol.Optional('user_input'): object,
})

WS_TYPE_DEPOSE_MFA = 'auth/depose_mfa'
SCHEMA_WS_DEPOSE_MFA = websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend({
    vol.Required('type'): WS_TYPE_DEPOSE_MFA,
    vol.Required('mfa_module_id'): str,
})

DATA_SETUP_FLOW_MGR = 'auth_mfa_setup_flow_manager'

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass):
    """Init mfa setup flow manager."""
    hass.components.websocket_api.async_register_command(
        WS_TYPE_SETUP_MFA, websocket_setup_mfa, SCHEMA_WS_SETUP_MFA)

    hass.components.websocket_api.async_register_command(
        WS_TYPE_DEPOSE_MFA, websocket_depose_mfa, SCHEMA_WS_DEPOSE_MFA)

    async def _async_create_setup_flow(handler, context, data):
        """Create a setup flow. hanlder is a mfa module"""
        mfa_module = hass.auth.get_auth_mfa_module(handler)
        if mfa_module is None:
            raise ValueError('Mfa module {} is not found'.format(handler))

        user_id = data.pop('user_id')
        return await mfa_module.async_setup_flow(user_id)

    async def _async_finish_setup_flow(flow, flow_result):
        _LOGGER.debug('flow_result: %s', flow_result)
        return flow_result

    hass.data[DATA_SETUP_FLOW_MGR] = data_entry_flow.FlowManager(
        hass, _async_create_setup_flow, _async_finish_setup_flow)


@callback
def websocket_setup_mfa(hass, connection, msg):
    """Return a setup flow for mfa auth module."""
    user = connection.request.get('hass_user')
    if user is None:
        connection.to_write.put_nowait(websocket_api.error_message(
            msg['id'], 'no_user', 'Not authenticated as a user'))
        return
    if user.system_generated:
        connection.to_write.put_nowait(websocket_api.error_message(
            msg['id'], 'no_system_user', 'System user cannot enable MFA'))
        return

    async def async_setup_flow(msg):
        """Helper to return a setup flow for mfa auth module."""
        flow_manager = hass.data.get(DATA_SETUP_FLOW_MGR)
        if flow_manager is None:
            connection.to_write.put_nowait(websocket_api.error_message(
                msg['id'], 'not_init',
                'Setup flow manager is not initialized.'))
            return

        flow_id = msg.get('flow_id')
        if flow_id is not None:
            result = await flow_manager.async_configure(
                flow_id, msg.get('user_input'))

        else:
            mfa_module_id = msg.get('mfa_module_id')
            mfa_module = hass.auth.get_auth_mfa_module(mfa_module_id)
            if mfa_module is None:
                connection.to_write.put_nowait(websocket_api.error_message(
                    msg['id'], 'no_module',
                    'MFA module {} is not found.'.format(
                        mfa_module_id
                    )))
                return

            result = await flow_manager.async_init(
                mfa_module_id, data={'user_id': user.id})

        connection.to_write.put_nowait(
            websocket_api.result_message(
                msg['id'], _prepare_result_json(result)))

    hass.async_add_job(async_setup_flow(msg))


@callback
def websocket_depose_mfa(hass, connection, msg):
    """Remove user from mfa module."""
    user = connection.request.get('hass_user')
    if user is None:
        connection.to_write.put_nowait(websocket_api.error_message(
            msg['id'], 'no_user', 'Not authenticated as a user'))
        return
    if user.system_generated:
        connection.to_write.put_nowait(websocket_api.error_message(
            msg['id'], 'no_system_user', 'System user cannot enable MFA'))
        return

    async def async_depose(msg):
        """Helper to disable user from mfa auth module."""
        mfa_module_id = msg['mfa_module_id']
        try:
            await hass.auth.async_disable_user_mfa(user, msg['mfa_module_id'])
        except Exception as err:
            connection.to_write.put_nowait(websocket_api.error_message(
                msg['id'], 'disable_failed',
                'Cannot disable Multi-factor Authentication Module'
                ' {}: {}'.format(mfa_module_id, err)))
            return

        connection.to_write.put_nowait(
            websocket_api.result_message(
                msg['id'], 'done'))

    hass.async_add_job(async_depose(msg))


def _prepare_result_json(result):
    """Convert result to JSON."""
    if result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY:
        data = result.copy()
        return data

    elif result['type'] != data_entry_flow.RESULT_TYPE_FORM:
        return result

    import voluptuous_serialize

    data = result.copy()

    schema = data['data_schema']
    if schema is None:
        data['data_schema'] = []
    else:
        data['data_schema'] = voluptuous_serialize.convert(schema)

    return data
