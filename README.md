# donelogger

A lightweight Python logging utility that **automatically measures elapsed time** between `[Start]` and `[Done]` markers. Built on top of Python's standard `logging` module — zero extra dependencies.

## Features

- **Automatic time tracking** — Wrap any block of work with `[Start:tag]` / `[Done:tag]` and get elapsed time for free
- **Multiple concurrent timers** — Use named tags to track overlapping tasks independently
- **Drop-in replacement** — Works just like `logging.getLogger()`, fully compatible with existing code
- **File logging** — Optional `RotatingFileHandler` with log rotation out of the box
- **Singleton logger management** — Same name always returns the same logger instance

## Installation

```bash
pip install git+https://github.com/rkskmt/donelogger.git
```

Or install locally:

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
# Output: -[Done data_load(2.001s)] Finished loading

logger.info("[Go:train] Training model")
time.sleep(1)
logger.info("[Done:train]")
# Output: -[Done train(1.002s)]
```

## Usage

### Basic Timer (No Tag Required)

For simple use cases, **tags are completely optional**. Just use `[Start]` / `[Done]` without any tag name:

```python
logger.info("[Start] Processing")
# ... your work here ...
logger.info("[Done] Complete")
# Output: -[Done Job(0.512s)] Complete
```

### Named Tags for Overlapping Tasks

Use named tags to track multiple tasks concurrently. Tags can overlap freely:

```python
logger.info("[Start:download] Downloading files")
logger.info("[Start:parse] Parsing config")

# ... work ...

logger.info("[Done:parse] Config ready")      # parse timer stops
logger.info("[Done:download] Files saved")     # download timer stops
```

### Cross-Module Timing

Timer state is shared globally at the class level, so you can **start a timer in one source file and stop it in another**:

```python
# === data_loader.py ===
from donelogger import getLogger
logger = getLogger()
logger.info("[Start:pipeline] Begin data pipeline")

# === trainer.py ===
from donelogger import getLogger
logger = getLogger()
# ... after all processing ...
logger.info("[Done:pipeline] Pipeline complete")
# Output: -[Done pipeline(42.3s)] Pipeline complete
```

This works because the timing dictionary is a class-level variable shared across all logger instances in the process.

### Regular Logging

All standard logging methods work as expected:

```python
logger.info("Normal log message")
logger.warning("This is a warning")
logger.error("Something went wrong")
```

### File Logging

Enable file output with log rotation:

```python
logger = getLogger(name="myapp", logfile="app.log")
```

### Custom Configuration

```python
logger = getLogger(
    name="myapp",
    logLevel=logging.DEBUG,
    logfile="app.log",
)
```

## Tag Syntax

| Marker | Description |
|---|---|
| `[Start]` or `[Go]` | Start the default timer |
| `[Start:tag]` or `[Go:tag]` | Start a named timer |
| `[Done]` | Stop the default timer and print elapsed time |
| `[Done:tag]` | Stop a named timer and print elapsed time |

Tags are case-insensitive for the keyword (`start`, `Start`, `go`, `Go`, `done`, `Done` all work).

## Output Format

```
+[Go data_load] Loading dataset...        ← timer started
-[Done data_load(2.001s)] Finished         ← timer stopped, elapsed shown
```

- `+` prefix indicates a timer start
- `-` prefix indicates a timer stop with elapsed time

## License

[MIT](LICENSE)