# Failover overhead

Run once against a healthy mock and once with `MOCK_FAIL_STATUS=500`; pass both
gateway URLs to compare the failure-path cost.
