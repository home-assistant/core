"""Custom API views for Home Assistant."""
import json
import logging
from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

class CustomAPIView(HomeAssistantView):
    """Custom API endpoint view."""
    
    url = "/api/custom"
    name = "api:custom"
    requires_auth = True  # Security: Require authentication
    
    async def get(self, request):
        """Handle GET requests."""
        _LOGGER.info("Received GET request to custom API")
        
        # Get query parameters
        params = dict(request.query)
        
        # Get Home Assistant instance
        hass: HomeAssistant = request.app["hass"]
        
        # Example: Get all entity states (with pagination to prevent memory issues)
        if params.get("action") == "get_states":
            try:
                limit = min(int(params.get("limit", 100)), 1000)  # Max 1000 entities
                offset = int(params.get("offset", 0))
                all_states = list(hass.states.async_all())
                paginated_states = all_states[offset:offset+limit]
                
                states = {}
                for state in paginated_states:
                    states[state.entity_id] = {
                        "state": state.state,
                        "attributes": dict(state.attributes)
                    }
                
                return web.json_response({
                    "success": True,
                    "data": states,
                    "pagination": {
                        "total": len(all_states),
                        "offset": offset,
                        "limit": limit,
                        "has_more": offset + limit < len(all_states)
                    }
                })
            except (ValueError, TypeError) as e:
                return web.json_response({
                    "success": False,
                    "error": f"Invalid pagination parameters: {str(e)}"
                }, status=400)
        
        # Example: Get specific entity state
        elif params.get("entity_id"):
            entity_id = params["entity_id"]
            state = hass.states.get(entity_id)
            if state:
                return web.json_response({
                    "success": True,
                    "data": {
                        "entity_id": entity_id,
                        "state": state.state,
                        "attributes": dict(state.attributes)
                    }
                })
            else:
                return web.json_response({
                    "success": False,
                    "error": f"Entity {entity_id} not found"
                }, status=404)
        
        # Default response
        return web.json_response({
            "success": True,
            "message": "Custom API endpoint is working",
            "available_actions": [
                "?action=get_states - Get all entity states",
                "?entity_id=ENTITY_ID - Get specific entity state"
            ]
        })
    
    async def post(self, request):
        """Handle POST requests."""
        _LOGGER.info("Received POST request to custom API")
        
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return web.json_response({
                "success": False,
                "error": "Invalid JSON in request body"
            }, status=400)
        
        # Get Home Assistant instance
        hass: HomeAssistant = request.app["hass"]
        
        # Handle different actions
        action = data.get("action")
        
        if action == "call_service":
            # Call a Home Assistant service with validation
            domain = data.get("domain")
            service = data.get("service")
            service_data = data.get("service_data", {})
            target = data.get("target", {})
            
            if not domain or not service:
                return web.json_response({
                    "success": False,
                    "error": "domain and service are required"
                }, status=400)
            
            # Validate domain and service names
            if not isinstance(domain, str) or not domain.replace("_", "").isalnum():
                return web.json_response({
                    "success": False,
                    "error": "Invalid domain name"
                }, status=400)
                
            if not isinstance(service, str) or not service.replace("_", "").isalnum():
                return web.json_response({
                    "success": False,
                    "error": "Invalid service name"
                }, status=400)
            
            # Check if service exists
            if not hass.services.has_service(domain, service):
                return web.json_response({
                    "success": False,
                    "error": f"Service {domain}.{service} not found"
                }, status=404)
            
            try:
                await hass.services.async_call(
                    domain, 
                    service, 
                    service_data, 
                    target=target
                )
                return web.json_response({
                    "success": True,
                    "message": f"Service {domain}.{service} called successfully"
                })
            except Exception as e:
                _LOGGER.error(f"Error calling service {domain}.{service}: {str(e)}")
                return web.json_response({
                    "success": False,
                    "error": f"Error calling service: {str(e)}"
                }, status=500)
        
        elif action == "set_state":
            # Set entity state
            entity_id = data.get("entity_id")
            state = data.get("state")
            attributes = data.get("attributes", {})
            
            if not entity_id or state is None:
                return web.json_response({
                    "success": False,
                    "error": "entity_id and state are required"
                }, status=400)
            
            hass.states.async_set(entity_id, state, attributes)
            return web.json_response({
                "success": True,
                "message": f"State set for {entity_id}"
            })
        
        else:
            return web.json_response({
                "success": False,
                "error": "Unknown action",
                "available_actions": [
                    "call_service - Call a Home Assistant service",
                    "set_state - Set an entity state"
                ]
            }, status=400)


class CustomWebhookView(HomeAssistantView):
    """Custom webhook endpoint."""
    
    url = "/api/webhook/custom"
    name = "api:webhook:custom"
    requires_auth = False
    
    async def post(self, request):
        """Handle webhook POST requests."""
        _LOGGER.info("Received webhook request")
        
        try:
            data = await request.json()
        except json.JSONDecodeError:
            # Try to get form data instead
            try:
                data = dict(await request.post())
            except Exception as e:
                _LOGGER.warning(f"Failed to parse form data: {str(e)}")
                data = {}
        
        # Get Home Assistant instance
        hass: HomeAssistant = request.app["hass"]
        
        # Fire an event that can be used in automations
        hass.bus.async_fire("custom_webhook", {
            "data": data,
            "headers": dict(request.headers),
            "remote": request.remote
        })
        
        # Log the webhook data
        _LOGGER.info(f"Webhook received data: {data}")
        
        return web.json_response({
            "success": True,
            "message": "Webhook received successfully"
        })
