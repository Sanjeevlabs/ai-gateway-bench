# Bifrost

The benchmark used Bifrost `v1.6.4` via its npx launcher. Convert
`config.yaml` to JSON as `config.json` in an application directory, then run:

```bash
npx -y @maximhq/bifrost --app-dir /tmp/gwbench-bifrost-run \
  --host 127.0.0.1 --port 8103
```

The Anthropic-compatible provider points at the local mock on port 9000 and is
benchmarked through Bifrost's native `/anthropic/v1/messages` route using the
`anthropic/mock` model name. Bifrost v1.6.4 does not mount this integration at
the root `/v1/messages` path; the benchmark records that native-prefix
limitation rather than using a proxy rewrite.
