# Portkey

Run the OSS Portkey gateway with `npx -y @portkey-ai/gateway`; the current
release listens on port 8787 by default. Send `x-portkey-provider: anthropic`
and `x-portkey-custom-host: http://127.0.0.1:9000` on `/v1/messages` requests.
The custom host routes to the local mock.
