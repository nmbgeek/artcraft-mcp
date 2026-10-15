use log::{debug, error, info, warn};

use crate::auth::load_credentials;
use crate::client::ArtCraftClient;
use crate::tools;
use crate::types::*;

pub struct McpServer {
    client: ArtCraftClient,
    initialized: bool,
}

impl McpServer {
    pub fn new() -> Self {
        let credentials = load_credentials();
        let client = ArtCraftClient::new(credentials);

        Self {
            client,
            initialized: false,
        }
    }

    pub async fn handle_request(&mut self, json_line: &str) -> Option<JsonRpcResponse> {
        let request: JsonRpcRequest = match serde_json::from_str(json_line) {
            Ok(req) => req,
            Err(e) => {
                error!("Failed to parse JSON-RPC request: {}", e);
                return Some(JsonRpcResponse::error(
                    None,
                    -32700,
                    format!("Parse error: {}", e),
                ));
            }
        };

        debug!("Received method: {}", request.method);

        if request.jsonrpc != "2.0" {
            return Some(JsonRpcResponse::error(request.id, -32600, "Invalid JSON-RPC version".into()));
        }
        if request.id.is_none() {
            if request.method == "notifications/initialized" {
                self.initialized = true;
                info!("MCP client initialized");
            }
            return None;
        }

        match request.method.as_str() {
            "initialize" => Some(self.handle_initialize(request)),
            "notifications/initialized" => {
                self.initialized = true;
                info!("MCP client initialized");
                None
            }
            "tools/list" => Some(self.handle_tools_list(request)),
            "tools/call" => Some(self.handle_tool_call(request).await),
            "ping" => Some(JsonRpcResponse::success(request.id, serde_json::json!({}))),
            _ => Some(JsonRpcResponse::error(
                request.id,
                -32601,
                format!("Method not found: {}", request.method),
            )),
        }
    }

    fn handle_initialize(&self, request: JsonRpcRequest) -> JsonRpcResponse {
        let params = request.params.as_ref();
        let requested = params.and_then(|p| p["protocolVersion"].as_str()).unwrap_or("");
        let protocol = match requested {
            "2024-11-05" | "2025-03-26" => requested,
            _ => "2025-03-26",
        };
        if let Some(client) = params.and_then(|p| p.get("clientInfo")) {
            info!("MCP client: {} version: {} protocol: {}", client["name"], client["version"], requested);
        }
        let result = InitializeResult {
            protocol_version: protocol.to_string(),
            capabilities: ServerCapabilities {
                tools: ToolCapabilities { list_changed: false },
            },
            server_info: ServerInfo {
                name: "artcraft-mcp".to_string(),
                version: "0.1.0".to_string(),
            },
        };

        JsonRpcResponse::success(
            request.id,
            serde_json::to_value(result).unwrap(),
        )
    }

    fn handle_tools_list(&self, request: JsonRpcRequest) -> JsonRpcResponse {
        let tools = tools::get_all_tools();
        let result = ToolsListResult { tools };

        JsonRpcResponse::success(
            request.id,
            serde_json::to_value(result).unwrap(),
        )
    }

    async fn handle_tool_call(&self, request: JsonRpcRequest) -> JsonRpcResponse {
        let params = match request.params {
            Some(p) => p,
            None => {
                return JsonRpcResponse::error(
                    request.id,
                    -32602,
                    "Missing params".to_string(),
                );
            }
        };

        let tool_request: ToolCallRequest = match serde_json::from_value(params) {
            Ok(req) => req,
            Err(e) => {
                return JsonRpcResponse::error(
                    request.id,
                    -32602,
                    format!("Invalid params: {}", e),
                );
            }
        };

        info!("Tool call: {}", tool_request.name);

        let result = tools::execute_tool(&tool_request.name, tool_request.arguments, &self.client).await;

        match result {
            Ok(content) => {
                let tool_result = ToolCallResult {
                    content,
                    is_error: Some(false),
                };
                JsonRpcResponse::success(
                    request.id,
                    serde_json::to_value(tool_result).unwrap(),
                )
            }
            Err(e) => {
                warn!("Tool {} failed: {}", tool_request.name, e);
                let tool_result = ToolCallResult {
                    content: vec![ToolContent {
                        content_type: "text".to_string(),
                        text: format!("Error: {}", e),
                    }],
                    is_error: Some(true),
                };
                JsonRpcResponse::success(
                    request.id,
                    serde_json::to_value(tool_result).unwrap(),
                )
            }
        }
    }
}
