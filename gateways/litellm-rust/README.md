# LiteLLM Rust

The Rust gateway is built from `/home/ubuntu/repos/litellm/litellm-rust` on
branch `litellm_rust_messages_route`.

```bash
cd /home/ubuntu/repos/litellm/litellm-rust
LITELLM_MASTER_KEY=gwbench \
LITELLM_CONFIG_PATH=/home/ubuntu/gatewaybench/gateways/litellm-rust/config.yaml \
PORT=8101 \
cargo run -p litellm-ai-gateway --features server,python-config
```

The benchmark config points Anthropic Messages at the local mock. The Python
config reader must be available to the embedded interpreter.
