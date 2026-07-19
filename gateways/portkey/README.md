# Portkey

Run the OSS Portkey gateway with `npx -y @portkey-ai/gateway`; the current
release listens on port 8787 by default. Send `x-portkey-provider: openai` and
`x-portkey-custom-host: http://127.0.0.1:9000/v1` on benchmark requests. The
custom host routes to the local mock.
