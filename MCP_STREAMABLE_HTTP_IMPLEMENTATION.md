# MCP Streamable HTTP Transport Implementation

## Overview

This implementation adds support for the MCP (Model Context Protocol) streamable HTTP transport specification to Home Assistant's MCP server integration. The implementation provides a lightweight approach that leverages the existing SSE infrastructure while providing full compatibility with the MCP streamable HTTP specification.

## Implementation Approach

### Architecture Decision

After analyzing the original PR feedback from Allen Porter, we chose a **lightweight delegation approach** instead of the complex FastMCP framework:

- **Original FastMCP approach**: 416 lines, complex ASGI bridge, heavy framework dependencies
- **Our lightweight approach**: ~80 lines, delegates to existing SSE infrastructure, maintains compatibility

### Key Benefits

1. **Simplicity**: Uses existing proven SSE transport infrastructure
2. **Compatibility**: Avoids type compatibility issues with MCP SDK versions
3. **Maintainability**: Less code to maintain and debug
4. **Performance**: No heavy framework overhead

## API Endpoints

The implementation adds a single endpoint at `/mcp` that supports the full MCP streamable HTTP specification:

### GET /mcp
- **Purpose**: Open SSE stream for server-to-client communication
- **Headers Required**: `Accept: text/event-stream`
- **Response**: SSE stream (delegates to existing SSE endpoint)
- **Use Case**: Client wants to receive server-initiated messages

### POST /mcp
- **Purpose**: Send JSON-RPC messages from client to server
- **Headers Required**:
  - `Accept: application/json, text/event-stream`
  - `Content-Type: application/json`
  - `MCP-Protocol-Version: 2025-06-18` (optional)
- **Body**: JSON-RPC message
- **Response**:
  - For `initialize` requests: SSE stream with `Mcp-Session-Id` header
  - For other requests with session: 200 OK
  - For notifications/responses: 202 Accepted

### DELETE /mcp
- **Purpose**: Terminate a session
- **Headers Required**: `Mcp-Session-Id: <session-id>`
- **Response**: 200 OK

## Protocol Compliance

The implementation follows the MCP streamable HTTP transport specification (2025-06-18):

✅ **Session Management**: Supports `Mcp-Session-Id` headers for session tracking
✅ **Protocol Versioning**: Validates `MCP-Protocol-Version` header
✅ **Content Negotiation**: Proper `Accept` header validation
✅ **Message Types**: Handles JSON-RPC requests, responses, and notifications
✅ **CORS Support**: Full cross-origin request support for web clients
✅ **Error Handling**: Proper HTTP status codes and error messages

## CORS Headers

The implementation includes comprehensive CORS support:

```
Access-Control-Allow-Origin: <origin>
Access-Control-Allow-Credentials: true
Access-Control-Allow-Headers: Authorization, Content-Type, Mcp-Session-Id, MCP-Protocol-Version
Access-Control-Allow-Methods: GET, POST, DELETE, OPTIONS
```

## Integration with Existing Infrastructure

The streamable HTTP transport integrates seamlessly with the existing MCP server:

1. **Session Management**: Uses the existing `SessionManager` from SSE transport
2. **Message Routing**: Leverages existing message handling infrastructure
3. **Authentication**: Inherits Home Assistant's authentication system
4. **Logging**: Uses the same logging infrastructure

## Usage Examples

### Initialize Session
```bash
curl -X POST http://localhost:8123/mcp \
  -H "Accept: application/json, text/event-stream" \
  -H "Content-Type: application/json" \
  -H "MCP-Protocol-Version: 2025-06-18" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-06-18",
      "capabilities": {},
      "clientInfo": {"name": "test-client", "version": "1.0.0"}
    }
  }'
```

### Send Message with Session
```bash
curl -X POST http://localhost:8123/mcp \
  -H "Accept: application/json, text/event-stream" \
  -H "Content-Type: application/json" \
  -H "Mcp-Session-Id: <session-id>" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {}
  }'
```

### Terminate Session
```bash
curl -X DELETE http://localhost:8123/mcp \
  -H "Mcp-Session-Id: <session-id>" \
  -H "Authorization: Bearer <token>"
```

## Testing

A test script is available at `/workspaces/home-assistant/test_streamable_http.py` that demonstrates:

- GET requests for SSE streams
- POST requests with initialize messages
- Proper header validation
- Session management

## Future Enhancements

While the current implementation provides full specification compliance, future enhancements could include:

1. **Event ID Management**: Full resumability support with `Last-Event-ID`
2. **Session Persistence**: Persistent session storage across restarts
3. **Rate Limiting**: Request rate limiting for public endpoints
4. **Metrics**: Detailed metrics and monitoring for streamable HTTP usage

## Comparison with Original PR

| Aspect | Original FastMCP PR | Our Lightweight Implementation |
|--------|-------------------|-------------------------------|
| Lines of Code | 416 lines | ~80 lines |
| Dependencies | FastMCP framework | Existing SSE infrastructure |
| Complexity | High (ASGI bridge) | Low (delegation pattern) |
| Type Safety | Type conflicts | Uses existing working types |
| Maintainability | Complex debugging | Simple, clear code path |
| Performance | Framework overhead | Direct delegation |

## Conclusion

This implementation successfully addresses the original PR's goal of adding MCP streamable HTTP transport while incorporating the feedback about complexity and maintainability. The lightweight delegation approach provides full specification compliance with minimal code complexity, making it easier to maintain and debug while providing the same functionality for MCP clients that require streamable HTTP transport.