use std::io::Write;
use std::process::{Command, Stdio};
use serde_json::{json, Value};

#[test]
fn native_stdio_contract_without_network() {
    let mut child = Command::new(env!("CARGO_BIN_EXE_artcraft-mcp"))
        .stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped())
        .spawn().unwrap();
    let messages = [
        json!({"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1"}}}),
        json!({"jsonrpc":"2.0","method":"notifications/initialized"}),
        json!({"jsonrpc":"2.0","method":"notifications/cancelled","params":{"requestId":99}}),
        json!({"jsonrpc":"2.0","id":2,"method":"tools/list"}),
        json!({"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"artcraft_list_image_models","arguments":{}}}),
        json!({"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"does_not_exist","arguments":{}}}),
        json!({"jsonrpc":"2.0","id":5,"method":"ping"}),
    ];
    let mut stdin = child.stdin.take().unwrap();
    for message in messages { writeln!(stdin, "{message}").unwrap(); }
    writeln!(stdin, "not json").unwrap();
    drop(stdin);
    let output = child.wait_with_output().unwrap();
    assert!(output.status.success());
    let replies: Vec<Value> = String::from_utf8(output.stdout).unwrap().lines()
        .map(|line| serde_json::from_str(line).unwrap()).collect();
    assert_eq!(replies.len(), 6, "Notifications must not produce responses");
    assert_eq!(replies[0]["result"]["protocolVersion"], "2024-11-05");
    assert_eq!(replies[0]["result"]["serverInfo"]["name"], "artcraft-mcp");
    assert_eq!(replies[0]["result"]["capabilities"]["tools"]["listChanged"], false);
    let tools = replies[1]["result"]["tools"].as_array().unwrap();
    assert_eq!(tools.len(), 61);
    for tool in tools {
        assert_eq!(tool["inputSchema"]["type"], "object", "{}", tool["name"]);
        assert!(tool.get("input_schema").is_none());
    }
    assert_eq!(replies[2]["result"]["isError"], false);
    assert_eq!(replies[2]["result"]["content"][0]["type"], "text");
    assert_eq!(replies[3]["result"]["isError"], true);
    assert_eq!(replies[4]["result"], json!({}));
    assert_eq!(replies[5]["error"]["code"], -32700);
}
