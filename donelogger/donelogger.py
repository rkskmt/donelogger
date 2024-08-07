import time
import logging
from logging.handlers import RotatingFileHandler
import sys
import re


class DoneloggerStreamHandler(logging.StreamHandler):

    def emit(self, record: logging.LogRecord) -> None:
        msg = str(record.__dict__.get("msg", ""))  # msg might be an error object
        self.terminator = '\n'
        super().emit(record)
        self.flush()  # Add this line to flush after each log message    
    

class DoneloggerFormatter(logging.Formatter):

    lastTime = time.time()
    isBenchmarked = False
    isJustBihindBenchmarked = False
    start_pattern = re.compile("^\[([S|s]tart|[G|g]o)(:?.*?)\]")
    done_pattern = re.compile("^\[[D|d]one(:?.*?)\]")
    tag2time = dict()
    default_job_name = "Job"

    def format(self, record: logging.LogRecord) -> str:

        if record.__dict__["levelname"] != "INFO":
            return super().format(record)

        msg = str(record.__dict__.get("msg", "")) # msg maight be error object
        
        start = self.start_pattern.match(msg)
        if start:
            tag = start.group(2)[1:] if len(start.group(2)) != 0 else self.default_job_name
            self.tag2time[tag] = time.perf_counter()
            self.lastTime = record.__dict__["created"]
            record.__dict__["msg"] =  "+[Go {}] {}".format(tag, msg[len(start.group()):].strip())
            ret = super().format(record)

        else:
            done = self.done_pattern.match(msg)
            if done:
                tag = done.groups()[0][1:] if len(done.groups()[0]) != 0 else self.default_job_name
                dt = time.perf_counter() - self.tag2time[tag] if tag in self.tag2time else -1.0
                m, s = divmod(dt, 60)
                elapsed = f"{m:.0f}m{s:.3}s" if m > 0 else f"{s:.3}s"
                ret = "-[Done {}({})] {}".format(tag, elapsed, msg[len(done.group()):].strip()) if tag in self.tag2time else f"*LOG ERROR* ({tag} is not started) {self.tag2time}"
                record.__dict__["msg"] = ret
                ret = super().format(record)

            else:
                record.__dict__["msg"] = msg
                ret = super().format(record)


        return ret

class LoggerManager:
    _instance = None
    _initialized_logger_names = set()
    _initialized_logger_name2instance = {}
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_logger(self, name: str = "doneLogger", logLevel: int = logging.INFO, logfile: str = None, datefmt:str = '%(asctime)s|%(levelname)s|%(message)s', _FormatStyle:str ='%d/%m/%Y %H:%M:%S') -> logging.Logger:

        if name in self._initialized_logger_names:
            return self._initialized_logger_name2instance[name]

        if name == "root":
            logger = logging.getLogger()
        else:
            logger = logging.getLogger(name)


        logger.setLevel(logLevel)
        logger.propagate = False

        # ハンドラーの設定
        self._setup_stream_handler(logger, datefmt, _FormatStyle)
        if logfile:
            self._setup_file_handler(logger, logfile)

        self._initialized_logger_names.add(name)
        self._initialized_logger_name2instance[name] = logger
        return logger

    def _setup_stream_handler(self, logger, datefmt, _FormatStyle):
        dlsh = DoneloggerStreamHandler(stream=sys.stdout)
        dllf = DoneloggerFormatter(datefmt, _FormatStyle)
        dlsh.setFormatter(dllf)
        logger.addHandler(dlsh)

    def _setup_file_handler(self, logger, logfile):
        fh = RotatingFileHandler(logfile, maxBytes=1000000, backupCount=2, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh_formatter = logging.Formatter('%(asctime)s %(levelname)s %(filename)s %(name)s %(funcName)s %(message)s')
        fh.setFormatter(fh_formatter)
        logger.addHandler(fh)

def getLogger(*args, **kwargs):
    return LoggerManager.get_instance().get_logger(*args, **kwargs)


if __name__ == "__main__":


    logger = getLogger()
    print(logging.Logger.manager.loggerDict)
    logger = getLogger()
    logger.info("[done] comment")
    logger.info("[Go:log] comment")
    logger.info("[Go:test] comment]") # last ]  should not be matched
    
    logger.info("[done:test] comment")
    logger.info(f'[Done:split]')
    logger.info(f'^^^ picked frames')

    logger.info("[Go] comment")
    
    logger.info("[done] comment")
    
    logger.info("[done:log] comment")
    logger.info("[done:log] comment")
    
    logger.warning("warn")
    logger.info("[Start] comment")
    time.sleep(1)
    logger.info("[Done] done message")
    logger.info("[Start:tag1]")
    logger.info("normal msg1")
    time.sleep(1)
    logger.info("[Done:tag1] ")
    logger.info("[Done:tag2] tag2 is not defined")
    logger.info("normal msg2")
    logger.info("normal msg3")
    logger.info("[Done:tag1] ")
    logger.info("normal msg4")
    logger.info("[Go:tag2] Go")
    logger.info("[Start] Start")
    time.sleep(1)
    logger.info("[Done]")
    logger.info("[Done:tag2]")


