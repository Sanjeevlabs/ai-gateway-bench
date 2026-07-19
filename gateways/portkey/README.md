# Portkey

Run the OSS Portkey gateway with `npx -y @portkey-ai/gateway`; the current
release listens on port 8787 by default. Send `x-portkey-provider: anthropic`
and `x-portkey-custom-host: http://127.0.0.1:9000/v1` on `/v1/messages`
requests. The custom host routes to the local mock's `/v1/messages` path.
The OSS release currently returns HTTP 500 for streaming Anthropic requests;
the session and single-call non-streaming measurements record that limitation
instead of fabricating streaming values.
