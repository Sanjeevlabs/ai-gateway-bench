#![forbid(unsafe_code)]

use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use std::sync::Arc;
use std::time::Instant;

use hdrhistogram::Histogram;
use reqwest::header::{HeaderMap, HeaderName, HeaderValue};
use reqwest::Method;
use serde_json::json;

struct Config {
    url: String,
    method: Method,
    headers: HeaderMap,
    body: Option<String>,
    requests: usize,
    concurrency: usize,
    warmup: usize,
    label: String,
    out: Option<String>,
}

fn parse_args() -> Config {
    let mut url = None;
    let mut method = Method::POST;
    let mut headers = HeaderMap::new();
    let mut body = None;
    let mut requests = 2000_usize;
    let mut concurrency = 16_usize;
    let mut warmup = 200_usize;
    let mut label = "target".to_string();
    let mut out = None;

    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        let mut value = || args.next().expect("flag requires a value");
        match arg.as_str() {
            "--url" => url = Some(value()),
            "--method" => method = value().parse().expect("valid HTTP method"),
            "--header" => {
                let raw = value();
                let (name, val) = raw.split_once(':').expect("header must be 'Name: value'");
                headers.insert(
                    name.trim().parse::<HeaderName>().expect("valid header name"),
                    val.trim().parse::<HeaderValue>().expect("valid header value"),
                );
            }
            "--body" => body = Some(value()),
            "--body-file" => {
                body = Some(std::fs::read_to_string(value()).expect("body file readable"))
            }
            "--requests" => requests = value().parse().expect("requests is a number"),
            "--concurrency" => concurrency = value().parse().expect("concurrency is a number"),
            "--warmup" => warmup = value().parse().expect("warmup is a number"),
            "--label" => label = value(),
            "--out" => out = Some(value()),
            other => panic!("unknown flag: {other}"),
        }
    }

    Config {
        url: url.expect("--url is required"),
        method,
        headers,
        body,
        requests,
        concurrency,
        warmup,
        label,
        out,
    }
}

struct Shared {
    remaining: AtomicUsize,
    errors: AtomicU64,
    client: reqwest::Client,
    config: Config,
}

async fn one_request(shared: &Shared) -> Option<u64> {
    let mut builder = shared
        .client
        .request(shared.config.method.clone(), &shared.config.url)
        .headers(shared.config.headers.clone());
    if let Some(body) = &shared.config.body {
        builder = builder.body(body.clone());
    }
    let start = Instant::now();
    match builder.send().await {
        Ok(response) => {
            let status = response.status();
            // Drain the body so the full round trip (not just headers) is timed.
            let _ = response.bytes().await;
            let elapsed_us = start.elapsed().as_micros() as u64;
            if status.is_success() {
                Some(elapsed_us)
            } else {
                shared.errors.fetch_add(1, Ordering::Relaxed);
                None
            }
        }
        Err(_) => {
            shared.errors.fetch_add(1, Ordering::Relaxed);
            None
        }
    }
}

#[tokio::main(flavor = "multi_thread")]
async fn main() {
    let config = parse_args();
    let client = reqwest::Client::builder()
        .pool_max_idle_per_host(config.concurrency)
        .build()
        .expect("client builds");

    // Warmup: fire `warmup` requests, discard their timings, then measure.
    let warmup_requests = config.warmup;
    let measured_requests = config.requests;
    let concurrency = config.concurrency;
    let label = config.label.clone();
    let out = config.out.clone();

    let shared = Arc::new(Shared {
        remaining: AtomicUsize::new(warmup_requests),
        errors: AtomicU64::new(0),
        client,
        config,
    });

    run_phase(&shared, concurrency, None).await;

    shared.remaining.store(measured_requests, Ordering::Relaxed);
    shared.errors.store(0, Ordering::Relaxed);
    let mut histogram = Histogram::<u64>::new(3).expect("histogram");
    let wall_start = Instant::now();
    run_phase(&shared, concurrency, Some(&mut histogram)).await;
    let wall = wall_start.elapsed().as_secs_f64();

    let errors = shared.errors.load(Ordering::Relaxed);
    let count = histogram.len();
    let rps = count as f64 / wall;
    let us_to_ms = |v: u64| v as f64 / 1000.0;
    let p50 = us_to_ms(histogram.value_at_quantile(0.50));
    let p90 = us_to_ms(histogram.value_at_quantile(0.90));
    let p99 = us_to_ms(histogram.value_at_quantile(0.99));
    let p999 = us_to_ms(histogram.value_at_quantile(0.999));
    let max = us_to_ms(histogram.max());
    let mean = histogram.mean() / 1000.0;

    println!(
        "{label:<22} n={count:<6} conc={concurrency:<4} rps={rps:>8.0}  \
         p50={p50:>7.3}ms  p90={p90:>7.3}ms  p99={p99:>7.3}ms  p99.9={p999:>7.3}ms  max={max:>8.3}ms  mean={mean:>7.3}ms  errors={errors}"
    );

    if let Some(path) = out {
        let record = json!({
            "label": label,
            "count": count,
            "concurrency": concurrency,
            "rps": rps,
            "p50_ms": p50,
            "p90_ms": p90,
            "p99_ms": p99,
            "p999_ms": p999,
            "max_ms": max,
            "mean_ms": mean,
            "errors": errors,
        });
        use std::io::Write;
        let mut file = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(path)
            .expect("results file opens");
        writeln!(file, "{record}").expect("write result line");
    }
}

async fn run_phase(shared: &Arc<Shared>, concurrency: usize, mut histogram: Option<&mut Histogram<u64>>) {
    let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel::<u64>();
    let mut workers = Vec::with_capacity(concurrency);
    for _ in 0..concurrency {
        let shared = Arc::clone(shared);
        let tx = tx.clone();
        workers.push(tokio::spawn(async move {
            loop {
                let current = shared.remaining.load(Ordering::Relaxed);
                if current == 0 {
                    break;
                }
                if shared
                    .remaining
                    .compare_exchange_weak(
                        current,
                        current - 1,
                        Ordering::Relaxed,
                        Ordering::Relaxed,
                    )
                    .is_err()
                {
                    continue;
                }
                if let Some(us) = one_request(&shared).await {
                    let _ = tx.send(us);
                }
            }
        }));
    }
    drop(tx);

    while let Some(us) = rx.recv().await {
        if let Some(histogram) = histogram.as_deref_mut() {
            histogram.record(us).expect("record latency");
        }
    }
    for worker in workers {
        let _ = worker.await;
    }
}
