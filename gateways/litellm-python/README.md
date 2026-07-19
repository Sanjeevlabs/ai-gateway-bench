# LiteLLM Python v1

Install `litellm[proxy]`, then run:

```bash
LITELLM_MASTER_KEY=gwbench litellm \
  --config gateways/litellm-python/config.yaml --port 8102
```

The config routes OpenAI Chat Completions to the local deterministic mock.
