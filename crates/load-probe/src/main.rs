#![forbid(unsafe_code)]

use std::env;
use std::sync::Arc;
use std::time::Instant;

use reqwest::header::{HeaderMap, HeaderName, HeaderValue};
use serde_json::{json, Value};
use tokio::sync::Semaphore;

#[derive(Clone)]
struct Config {
    label: String,
    url: String,
    count: usize,
    concurrency: usize,
    headers: HeaderMap,
    body: Value,
    output: String,
}

fn argument(name: &str) -> String {
    let mut args = env::args().skip(1);
    while let Some(value) = args.next() {
        if value == name {
            return args
                .next()
                .unwrap_or_else(|| panic!("missing value for {name}"));
        }
    }
    panic!("missing required argument {name}");
}

fn optional_argument(name: &str, default: &str) -> String {
    let mut args = env::args().skip(1);
    while let Some(value) = args.next() {
        if value == name {
            return args
                .next()
                .unwrap_or_else(|| panic!("missing value for {name}"));
        }
    }
    default.to_string()
}

fn headers() -> HeaderMap {
    let mut result = HeaderMap::new();
    let mut args = env::args().skip(1);
    while let Some(value) = args.next() {
        if value == "--header" {
            let header = args
                .next()
                .unwrap_or_else(|| panic!("missing value for --header"));
            let (name, value) = header
                .split_once(':')
                .unwrap_or_else(|| panic!("invalid header {header}"));
            result.insert(
                HeaderName::from_bytes(name.trim().as_bytes()).expect("valid header name"),
                HeaderValue::from_str(value.trim()).expect("valid header value"),
            );
        }
    }
    result
}

fn percentile(values: &mut [f64], quantile: f64) -> f64 {
    values.sort_by(f64::total_cmp);
    let index = ((values.len() - 1) as f64 * quantile).round() as usize;
    values[index]
}

#[tokio::main]
async fn main() {
    let config = Config {
        label: argument("--label"),
        url: argument("--url"),
        count: optional_argument("--count", "1000")
            .parse()
            .expect("valid count"),
        concurrency: optional_argument("--concurrency", "1")
            .parse()
            .expect("valid concurrency"),
        headers: headers(),
        body: json!({
            "model": optional_argument("--model", "anthropic/mock"),
            "max_tokens": 40,
            "stream": false,
            "messages": [{"role": "user", "content": "token ".repeat(32)}],
        }),
        output: argument("--output"),
    };
    let client = reqwest::Client::builder()
        .pool_max_idle_per_host(config.concurrency)
        .build()
        .expect("build HTTP client");
    let semaphore = Arc::new(Semaphore::new(config.concurrency));
    let started = Instant::now();
    let jobs = (0..config.count)
        .map(|_| {
            let client = client.clone();
            let semaphore = semaphore.clone();
            let url = config.url.clone();
            let headers = config.headers.clone();
            let body = config.body.clone();
            tokio::spawn(async move {
                let _permit = semaphore
                    .acquire_owned()
                    .await
                    .expect("semaphore remains open");
                let request_started = Instant::now();
                let response = client.post(url).headers(headers).json(&body).send().await;
                let latency_ms = request_started.elapsed().as_secs_f64() * 1000.0;
                match response {
                    Ok(response) if response.status().is_success() => (latency_ms, None),
                    Ok(response) => (
                        latency_ms,
                        Some(format!("HTTP {}", response.status().as_u16())),
                    ),
                    Err(error) => (latency_ms, Some(error.to_string())),
                }
            })
        })
        .collect::<Vec<_>>();
    let mut latencies = Vec::with_capacity(config.count);
    let mut errors = Vec::new();
    for job in jobs {
        let (latency_ms, error) = job.await.expect("load task completes");
        latencies.push(latency_ms);
        if let Some(error) = error {
            errors.push(error);
        }
    }
    let elapsed_s = started.elapsed().as_secs_f64();
    let p50_ms = percentile(&mut latencies, 0.50);
    let p99_ms = percentile(&mut latencies, 0.99);
    let result = json!({
        "label": config.label,
        "url": config.url,
        "count": config.count,
        "concurrency": config.concurrency,
        "elapsed_s": elapsed_s,
        "rps": config.count as f64 / elapsed_s,
        "latency_p50_ms": p50_ms,
        "latency_p99_ms": p99_ms,
        "errors": errors,
    });
    std::fs::write(
        config.output,
        serde_json::to_string_pretty(&result).expect("serialize result") + "\n",
    )
    .expect("write result");
    println!("{result}");
}
