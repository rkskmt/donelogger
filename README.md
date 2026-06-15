# donelogger

**Stop writing `time.time()` bookkeeping. Just log `[Start]` and `[Done]`.**

donelogger is a tiny drop-in wrapper around Python's standard `logging` that
**automatically measures and prints the elapsed time** between `[Start]` and
`[Done]` markers in your log messages — no timer variables, no `f"{...:.3f}s"`
math, no extra dependencies.

```python
logger.info("[Start:train] Training model...")
train()
logger.info("[Done:train] Finished")
# 15/06/2026 12:25:04|INFO|+[Go train] Training model...
# 15/06/2026 12:25:04|INFO|-[Done train(1m23.40s)] Finished
```

> Battle-tested: donelogger runs in production internal tooling, where knowing
> "how long did each stage take?" across a long pipeline matters every day.

---

## Why donelogger?

Timing a block of work the usual way means scattering bookkeeping all over your
code:

```python
# Before — manual, repetitive, easy to get wrong
t0 = time.perf_counter()
logger.info("Loading dataset...")
load_dataset()
logger.info(f"Finished loading in {time.perf_counter() - t0:.3f}s")

t1 = time.perf_counter()              # another stopwatch variable to track
logger.info("Training model...")
train()
logger.info(f"Training done in {time.perf_counter() - t1:.3f}s")
```

With donelogger the timing *is* the log line — the stopwatch is implicit:

```python
# After — the log reads naturally and the timing is automatic
logger.info("[Start:load]  Loading dataset...")
load_dataset()
logger.info("[Done:load]   Finished loading")

logger.info("[Start:train] Training model...")
train()
logger.info("[Done:train]  Training done")
```

No `t0`/`t1` variables to mismatch, no per-call formatting to keep consistent,
and the elapsed time is rendered in a human-friendly unit automatically.

## Features

- **Zero-boilerplate timing** — wrap work in `[Start:tag]` / `[Done:tag]` and get the elapsed time for free.
- **Reads like normal logs** — markers are just text at the front of your message; nothing new to learn.
- **Named tags** — time overlapping or nested stages independently (`download`, `parse`, `train`, …).
- **Cross-module** — start a timer in one file and finish it in another, as long as they share a logger name.
- **Human-friendly durations** — adaptive units from microseconds to hours (`300us`, `512.0ms`, `1.003s`, `1m15.40s`, `1h15m00s`), or force fixed seconds.
- **Drop-in `logging`** — `getLogger()` returns a real `logging.Logger`; all the usual `.info()` / `.warning()` / `.error()` work unchanged.
- **Optional rotating file log** — one argument enables a `RotatingFileHandler` with a detailed format.
- **Zero dependencies** — pure standard library, built on `logging.Formatter`.

## Installation

```bash
pip install git+https://github.com/rkskmt/donelogger.git
```

Or install locally for development:

```bash
git clone https://github.com/rkskmt/donelogger.git
cd donelogger
pip install -e .
```

## Quick Start

```python
import time
from donelogger import getLogger

logger = getLogger()

logger.info("[Start:data_load] Loading dataset...")
time.sleep(2)
logger.info("[Done:data_load] Finished loading")
# -> -[Done data_load(2.001s)] Finished loading

logger.info("[Go:train] Training model")   # [Go] is an alias for [Start]
time.sleep(1)
logger.info("[Done:train]")
# -> -[Done train(1.002s)]
```

## Usage

### Default timer (no tag required)

Tags are optional. Bare `[Start]` / `[Done]` use a default timer named `Job`:

```python
logger.info("[Start] Processing")
# ... work ...
logger.info("[Done] Complete")
# -> -[Done Job(512.0ms)] Complete
```

### Named tags for overlapping / nested work

Use named tags to track multiple timers at once. They can overlap or nest freely:

```python
logger.info("[Start:download] Downloading files")
logger.info("[Start:parse]    Parsing config")
# ... work ...
logger.info("[Done:parse]    Config ready")    # parse timer stops
logger.info("[Done:download] Files saved")     # download timer stops
```

### Cross-module timing

`getLogger(name=...)` returns the **same logger instance** for a given name
(process-wide singleton), and the timer state lives on that logger. So any
module that calls `getLogger()` with the same name shares the same timers —
**start in one file, finish in another**:

```python
# === data_loader.py ===
from donelogger import getLogger
getLogger().info("[Start:pipeline] Begin data pipeline")

# === trainer.py ===
from donelogger import getLogger
# ... after all stages finish ...
getLogger().info("[Done:pipeline] Pipeline complete")
# -> -[Done pipeline(42.300s)] Pipeline complete
```

Loggers created with **different names keep independent timers**, so unrelated
components never clobber each other's tags.

### Regular logging

Everything that isn't a marker passes straight through — donelogger is a normal
logger:

```python
logger.info("Just a normal message")
logger.warning("This is a warning")
logger.error("Something went wrong")
```

(Only `INFO`-level messages are scanned for markers; other levels are never
touched.)

### Choosing the elapsed-time format

`elapsed_style` controls how durations are rendered (default `"adaptive"`):

```python
logger = getLogger(elapsed_style="adaptive")  # 300us, 512.0ms, 1.003s, 1m15.40s, 1h15m00s
logger = getLogger(elapsed_style="seconds")   # always seconds: 0.300s, 0.512s, 1.003s, 75.400s
```

### File logging

Pass `logfile=` to also write to a rotating file (1 MB × 2 backups) with a
detailed, machine-friendly format:

```python
logger = getLogger(name="myapp", logfile="app.log")
```

### Full configuration

```python
import logging
from donelogger import getLogger

logger = getLogger(
    name="myapp",
    logLevel=logging.DEBUG,
    logfile="app.log",
    fmt="%(asctime)s|%(levelname)s|%(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
    elapsed_style="adaptive",
)
```

## Marker syntax

| Marker | Meaning |
|---|---|
| `[Start]` / `[Go]` | Start the default (`Job`) timer |
| `[Start:tag]` / `[Go:tag]` | Start a named timer |
| `[Done]` | Stop the default timer and print elapsed time |
| `[Done:tag]` | Stop a named timer and print elapsed time |

- The keyword is **case-insensitive** (`start`, `Start`, `go`, `Go`, `done`, `Done`).
- A marker is only recognized at the **very beginning** of the message.
- `[Done:tag]` without a prior `[Start:tag]` emits `*LOG ERROR* (tag is not started) {...}` so mistakes are obvious.
- A tag is not consumed on `[Done]`, so you can stop the same tag more than once (each reports elapsed since its `[Start]`).

## Output format

```
+[Go data_load] Loading dataset...      ← '+' = timer started
-[Done data_load(2.001s)] Finished      ← '-' = timer stopped, elapsed shown
```

**`adaptive`** (default) picks a unit by magnitude:

| Duration | Rendered |
|---|---|
| 300 µs | `300us` |
| 5 ms | `5.0ms` |
| 0.512 s | `512.0ms` |
| 1.003 s | `1.003s` |
| 75.4 s | `1m15.40s` |
| 4500 s | `1h15m00s` |

**`seconds`** always uses seconds (handy when you post-process logs):

| Duration | Rendered |
|---|---|
| 0.005 s | `0.005s` |
| 75.4 s | `1m15.400s` |
| 4500 s | `75m00.000s` |

## API

### `getLogger(name="doneLogger", logLevel=logging.INFO, logfile=None, fmt=..., datefmt=..., elapsed_style="adaptive")`

Returns a configured `logging.Logger`. Calling it again with the same `name`
returns the cached instance (so configuration only happens once).

| Parameter | Default | Description |
|---|---|---|
| `name` | `"doneLogger"` | Logger name. Same name → same instance (and shared timers). `"root"` configures the root logger. |
| `logLevel` | `logging.INFO` | Level for the console handler / logger. |
| `logfile` | `None` | If set, also log to this file via a rotating handler (1 MB × 2 backups). |
| `fmt` | `%(asctime)s\|%(levelname)s\|%(message)s` | Console log format (standard `logging` format string). |
| `datefmt` | `%d/%m/%Y %H:%M:%S` | Timestamp format. |
| `elapsed_style` | `"adaptive"` | `"adaptive"` (µs→h) or `"seconds"` (always seconds). |

The package also exposes `DoneloggerFormatter`, `DoneloggerStreamHandler`, and
`LoggerManager` for advanced/custom wiring. `DoneloggerFormatter` is a drop-in
`logging.Formatter` (the standard `fmt` / `datefmt` / `style` arguments still
work), with one extra keyword-only argument, `elapsed_style`.

## How it works

donelogger installs a custom `logging.Formatter` that inspects each `INFO`
message. A `[Start]`/`[Go]` marker records `time.perf_counter()` under the tag;
the matching `[Done]` looks it up, computes the delta, and rewrites the line
with the elapsed time. Because it's all in the formatter, your call sites stay
plain `logger.info(...)` calls and non-marker logging is unaffected.

## Testing

```bash
python -m unittest discover
```

The suite is dependency-free and mocks `time.perf_counter`, so the timing
assertions are deterministic (no `sleep`, no flakiness).

## License

[MIT](LICENSE)
