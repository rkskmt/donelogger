import os
import time
import logging
from logging.handlers import RotatingFileHandler
import sys
import re
import threading
from copy import copy
from typing import Optional


class DoneloggerStreamHandler(logging.StreamHandler):

    def emit(self, record: logging.LogRecord) -> None:
        self.terminator = '\n'
        super().emit(record)
    

class DoneloggerFormatter(logging.Formatter):

    start_pattern = re.compile(r"^\[(?:start|go)(:[^\]]*)?\]", re.IGNORECASE)
    done_pattern = re.compile(r"^\[done(:[^\]]*)?\]", re.IGNORECASE)
    default_job_name = "Job"

    def __init__(self, *args, elapsed_style: str = "adaptive", **kwargs):
        # keyword-only `elapsed_style` keeps this a drop-in logging.Formatter:
        # standard args (fmt/datefmt/style/validate) still flow to super().
        super().__init__(*args, **kwargs)
        self.tag2time = {}  # per-instance: tags are not shared across loggers
        self._timer_lock = threading.RLock()
        if elapsed_style not in ("adaptive", "seconds"):
            raise ValueError(f"elapsed_style must be 'adaptive' or 'seconds', got {elapsed_style!r}")
        self.elapsed_style = elapsed_style

    def _format_elapsed(self, dt: float) -> str:
        if self.elapsed_style == "seconds":  # always seconds, fixed 3 decimals
            m, s = divmod(dt, 60)
            return f"{m:.0f}m{s:06.3f}s" if m > 0 else f"{s:.3f}s"
        # "adaptive": pick a human-friendly unit by magnitude
        if dt < 1e-3:
            return f"{dt * 1e6:.0f}us"
        if dt < 1:
            return f"{dt * 1e3:.1f}ms"
        if dt < 60:
            return f"{dt:.3f}s"
        m, s = divmod(dt, 60)
        if m < 60:
            return f"{m:.0f}m{s:05.2f}s"
        h, m = divmod(m, 60)
        return f"{h:.0f}h{m:02.0f}m{s:02.0f}s"

    def format(self, record: logging.LogRecord) -> str:

        if record.levelno != logging.INFO:
            return super().format(record)

        # Expand logging's lazy %-arguments before inspecting markers. Work on a
        # shallow copy so this formatter cannot affect other handlers attached
        # to the same logger.
        msg = record.getMessage()

        start = self.start_pattern.match(msg)
        if start:
            tag_suffix = start.group(1)
            tag = tag_suffix[1:] if tag_suffix is not None else self.default_job_name
            with self._timer_lock:
                self.tag2time[tag] = time.perf_counter()
            rendered_msg = "+[Go {}] {}".format(tag, msg[len(start.group()):].strip())
        else:
            done = self.done_pattern.match(msg)
            if done:
                tag_suffix = done.group(1)
                tag = tag_suffix[1:] if tag_suffix is not None else self.default_job_name
                with self._timer_lock:
                    started_at = self.tag2time.get(tag)
                if started_at is not None:
                    dt = time.perf_counter() - started_at
                    elapsed = self._format_elapsed(dt)
                    rendered_msg = "-[Done {}({})] {}".format(tag, elapsed, msg[len(done.group()):].strip())
                else:
                    with self._timer_lock:
                        active_timers = dict(self.tag2time)
                    rendered_msg = f"*LOG ERROR* ({tag} is not started) {active_timers}"
            else:
                return super().format(record)

        formatted_record = copy(record)
        formatted_record.msg = rendered_msg
        formatted_record.args = ()
        return super().format(formatted_record)

DEFAULT_LOGGER_NAME = "doneLogger"
DEFAULT_LEVEL = logging.INFO
DEFAULT_FMT = '%(asctime)s|%(levelname)s|%(message)s'
DEFAULT_DATEFMT = '%d/%m/%Y %H:%M:%S'
DEFAULT_ELAPSED_STYLE = "adaptive"
# The file gets the caller location on top of the console format.
FILE_FMT = '%(asctime)s %(levelname)s %(filename)s %(name)s %(funcName)s %(message)s'


class LoggerManager:
    _instance = None
    _lock = threading.Lock()
    _initialized_logger_name2instance = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get_logger(
        self,
        name: str = DEFAULT_LOGGER_NAME,
        logLevel: Optional[int] = None,
        logfile: Optional[str] = None,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        elapsed_style: Optional[str] = None,
    ) -> logging.Logger:
        """Return the logger called `name`, creating it on first use.

        The logger is shared by every module that asks for the same name, so
        the first caller is usually an imported module using the defaults, not
        the program's entry point. Explicit settings are therefore applied on
        every call, not only the creating one: a later `logfile=` adds a file
        handler (once per path), and a later `logLevel` / `fmt` / `datefmt` /
        `elapsed_style` replaces the current value. Omitted arguments leave
        the existing configuration untouched.
        """
        with self._lock:
            logger = self._initialized_logger_name2instance.get(name)
            if logger is None:
                logger = logging.getLogger() if name == "root" else logging.getLogger(name)
                logger.setLevel(DEFAULT_LEVEL if logLevel is None else logLevel)
                logger.propagate = False
                self._setup_stream_handler(
                    logger,
                    DEFAULT_FMT if fmt is None else fmt,
                    DEFAULT_DATEFMT if datefmt is None else datefmt,
                    DEFAULT_ELAPSED_STYLE if elapsed_style is None else elapsed_style,
                )
                self._initialized_logger_name2instance[name] = logger
            else:
                if logLevel is not None:
                    logger.setLevel(logLevel)
                if fmt is not None or datefmt is not None or elapsed_style is not None:
                    self._reconfigure_formatters(logger, fmt, datefmt, elapsed_style)
            if logfile:
                self._setup_file_handler(logger, logfile)
            return logger

    def _setup_stream_handler(self, logger, fmt, datefmt, elapsed_style):
        dlsh = DoneloggerStreamHandler(stream=sys.stdout)
        dllf = DoneloggerFormatter(fmt, datefmt, elapsed_style=elapsed_style)
        dlsh.setFormatter(dllf)
        logger.addHandler(dlsh)

    def _setup_file_handler(self, logger, logfile: str):
        # Idempotent per path: asking again for a file that is already attached
        # must not duplicate every line.
        path = os.path.abspath(logfile)
        for handler in logger.handlers:
            if isinstance(handler, logging.FileHandler) and handler.baseFilename == path:
                return
        console_formatter = next(
            handler.formatter for handler in logger.handlers
            if isinstance(handler.formatter, DoneloggerFormatter)
        )
        fh = RotatingFileHandler(logfile, maxBytes=1000000, backupCount=2, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh_formatter = DoneloggerFormatter(FILE_FMT, elapsed_style=console_formatter.elapsed_style)
        # Share the timers with the console formatter so a file attached after
        # some [Start] lines still reports their [Done] elapsed times.
        fh_formatter.tag2time = console_formatter.tag2time
        fh_formatter._timer_lock = console_formatter._timer_lock
        fh.setFormatter(fh_formatter)
        logger.addHandler(fh)

    def _reconfigure_formatters(self, logger, fmt, datefmt, elapsed_style):
        # Rebuild each DoneloggerFormatter with the explicit values, keeping its
        # other settings and its running timers. fmt/datefmt are console-only,
        # like on the creating call; the file keeps FILE_FMT.
        for handler in logger.handlers:
            old = handler.formatter
            if not isinstance(old, DoneloggerFormatter):
                continue
            is_file = isinstance(handler, logging.FileHandler)
            new = DoneloggerFormatter(
                old._fmt if (fmt is None or is_file) else fmt,
                old.datefmt if (datefmt is None or is_file) else datefmt,
                elapsed_style=old.elapsed_style if elapsed_style is None else elapsed_style,
            )
            new.tag2time = old.tag2time
            new._timer_lock = old._timer_lock
            handler.setFormatter(new)

def getLogger(*args, **kwargs):
    return LoggerManager.get_instance().get_logger(*args, **kwargs)


if __name__ == "__main__":
    # Quick visual demo. Full verification lives in tests/test_donelogger.py.
    logger = getLogger()

    logger.info("[Start] build")
    time.sleep(0.3)
    logger.info("[Done] build finished")

    logger.info("[Start:fetch] downloading")
    time.sleep(0.1)
    logger.info("[Done:fetch] got it")

    logger.warning("a non-INFO line passes straight through")
    logger.info("a plain line passes straight through")
    logger.info("[Done:never-started] reports a LOG ERROR")


