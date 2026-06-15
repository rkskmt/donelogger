import time
import logging
from logging.handlers import RotatingFileHandler
import sys
import re
import threading
from typing import Optional


class DoneloggerStreamHandler(logging.StreamHandler):

    def emit(self, record: logging.LogRecord) -> None:
        msg = str(record.__dict__.get("msg", ""))  # msg might be an error object
        self.terminator = '\n'
        super().emit(record)
        self.flush()  # Add this line to flush after each log message    
    

class DoneloggerFormatter(logging.Formatter):

    start_pattern = re.compile(r"^\[([Ss]tart|[Gg]o)(:?.*?)\]")
    done_pattern = re.compile(r"^\[[Dd]one(:?.*?)\]")
    default_job_name = "Job"

    def __init__(self, *args, elapsed_style: str = "adaptive", **kwargs):
        # keyword-only `elapsed_style` keeps this a drop-in logging.Formatter:
        # standard args (fmt/datefmt/style/validate) still flow to super().
        super().__init__(*args, **kwargs)
        self.tag2time = {}  # per-instance: tags are not shared across loggers
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

        if record.__dict__["levelname"] != "INFO":
            return super().format(record)

        msg = str(record.__dict__.get("msg", ""))  # msg might be error object

        start = self.start_pattern.match(msg)
        if start:
            tag = start.group(2)[1:] if len(start.group(2)) != 0 else self.default_job_name
            self.tag2time[tag] = time.perf_counter()
            record.__dict__["msg"] = "+[Go {}] {}".format(tag, msg[len(start.group()):].strip())
        else:
            done = self.done_pattern.match(msg)
            if done:
                tag = done.groups()[0][1:] if len(done.groups()[0]) != 0 else self.default_job_name
                if tag in self.tag2time:
                    dt = time.perf_counter() - self.tag2time[tag]
                    elapsed = self._format_elapsed(dt)
                    record.__dict__["msg"] = "-[Done {}({})] {}".format(tag, elapsed, msg[len(done.group()):].strip())
                else:
                    record.__dict__["msg"] = f"*LOG ERROR* ({tag} is not started) {self.tag2time}"
            # else: not a start/done line — leave record.msg unchanged

        return super().format(record)

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

    def get_logger(self, name: str = "doneLogger", logLevel: int = logging.INFO, logfile: Optional[str] = None, fmt: str = '%(asctime)s|%(levelname)s|%(message)s', datefmt: str = '%d/%m/%Y %H:%M:%S', elapsed_style: str = "adaptive") -> logging.Logger:

        if name in self._initialized_logger_name2instance:
            return self._initialized_logger_name2instance[name]

        if name == "root":
            logger = logging.getLogger()
        else:
            logger = logging.getLogger(name)


        logger.setLevel(logLevel)
        logger.propagate = False

        # ハンドラーの設定
        self._setup_stream_handler(logger, fmt, datefmt, elapsed_style)
        if logfile:
            self._setup_file_handler(logger, logfile)

        self._initialized_logger_name2instance[name] = logger
        return logger

    def _setup_stream_handler(self, logger, fmt, datefmt, elapsed_style="adaptive"):
        dlsh = DoneloggerStreamHandler(stream=sys.stdout)
        dllf = DoneloggerFormatter(fmt, datefmt, elapsed_style=elapsed_style)
        dlsh.setFormatter(dllf)
        logger.addHandler(dlsh)

    def _setup_file_handler(self, logger, logfile: str):
        fh = RotatingFileHandler(logfile, maxBytes=1000000, backupCount=2, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh_formatter = logging.Formatter('%(asctime)s %(levelname)s %(filename)s %(name)s %(funcName)s %(message)s')
        fh.setFormatter(fh_formatter)
        logger.addHandler(fh)

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


