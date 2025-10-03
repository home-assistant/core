# MCP Streamable HTTP Transport Enhancement

## Overview
Enhanced the Model Context Protocol server component with proper event stream buffering and resumability support for the streamable HTTP transport endpoint.

## Key Features Implemented

### 1. Event Store Architecture
- **File**: `homeassistant/components/mcp_server/event_store.py`
- **Purpose**: Provides event buffering and replay functionality for resumability
- **Key Components**:
  - `EventStore` abstract base class defining the interface
  - `InMemoryEventStore` concrete implementation with configurable limits
  - `EventMessage` dataclass for structured event storage
  - Event ID generation using UUID4
  - Stream-based event organization
  - LRU eviction when hitting storage limits

### 2. Enhanced Streamable HTTP Endpoint
- **File**: `homeassistant/components/mcp_server/http.py` (enhanced)
- **Endpoint**: `/mcp` (as defined in `STREAMABLE_HTTP_API`)
- **Key Enhancements**:
  - Proper event buffering for all SSE messages
  - `Last-Event-ID` header support for client reconnection
  - Event replay functionality for missed events
  - Session-based event stream management
  - Full MCP protocol compliance
  - Enhanced CORS support including `Last-Event-ID` header

### 3. Resumability Support
- **Client Reconnection**: Clients can reconnect with `Last-Event-ID` header
- **Event Replay**: Missed events are replayed in order
- **Session Management**: Each session gets its own event stream
- **Cleanup**: Event streams are properly cleaned up on session termination

## Protocol Compliance

### MCP Streamable HTTP Specification
✅ **GET Requests**: SSE stream with event buffering and resumability
✅ **POST Requests**: JSON-RPC message processing with enhanced session management
✅ **DELETE Requests**: Session termination with event cleanup
✅ **CORS Support**: Full cross-origin request support
✅ **Header Validation**: Proper Accept and MCP-Protocol-Version validation
✅ **Event IDs**: All SSE events include unique IDs for resumability
✅ **Last-Event-ID**: Support for client-driven event replay

### Key Improvements over FastMCP Complexity
- **Lightweight Architecture**: Builds on existing Home Assistant SSE infrastructure
- **Delegation Pattern**: Reuses existing SSE implementation for compatibility
- **Targeted Enhancement**: Adds only the missing resumability features
- **Maintainable Code**: Clear separation of concerns with event store abstraction
- **Memory Management**: Configurable event limits to prevent memory leaks

## Implementation Details

### Event Flow
1. Client connects via GET request to `/mcp`
2. SSE stream established with session ID
3. All outgoing messages stored in event store with unique IDs
4. Client disconnection triggers event stream buffering
5. Client reconnection with `Last-Event-ID` replays missed events
6. Session cleanup removes stored events

### Memory Management
- Default limit: 1000 events per stream
- LRU eviction when limits exceeded
- Immediate cleanup on session termination
- Per-stream storage isolation

### Backward Compatibility
- Existing SSE endpoint (`/mcp_server/sse`) unchanged
- Existing message endpoint (`/mcp_server/messages`) unchanged
- New streamable HTTP endpoint operates independently
- No breaking changes to existing functionality

## Testing Considerations
- Event replay functionality should be tested with client disconnections
- Memory limits should be validated under high load
- CORS functionality should be tested with cross-origin requests
- Session cleanup should be verified for proper resource management

## Future Enhancements
- Persistent event storage (database-backed)
- Configurable event retention policies
- Event compression for large messages
- Metrics and monitoring for event store performance