# Bifrost

The benchmark used Bifrost `v1.6.4` via its npx launcher. Convert
`config.yaml` to JSON as `config.json` in an application directory, then run:

```bash
npx -y @maximhq/bifrost --app-dir /tmp/gwbench-bifrost-run \
  --host 127.0.0.1 --port 8103
```

The custom OpenAI-compatible provider points at the local mock on port 9000.
