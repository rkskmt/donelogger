import time
import logging
from logging.handlers import RotatingFileHandler
import sys
import re


class DoneloggerStreamHandler(logging.StreamHandler):

    def emit(self, record: logging.LogRecord) -> None:
        msg = str(record.__dict__.get("msg", "")) # msg maight be error object
        self.terminator = '\n'
        self.isBenchmarked = True

        return super().emit(record)

class DoneloggerFormatter(logging.Formatter):

    lastTime = time.time()
    isBenchmarked = False
    isJustBihindBenchmarked = False
    startMsg = "[Start]"
    doneMsg = "[Done]"
    start_pattern = re.compile("^\[[S|s]tart(:?.*)\]")
    done_pattern = re.compile("^\[[D|d]one(:?.*)\]")
    tag2time = dict()

    def format(self, record: logging.LogRecord) -> str:

        if record.__dict__["levelname"] != "INFO":
            return super().format(record)

        msg = str(record.__dict__.get("msg", "")) # msg maight be error object
        
        start = self.start_pattern.match(msg)
        if start:
            tag = start.groups()[0][1:] if len(start.groups()[0]) != 0 else "job"
            self.tag2time[tag] = time.perf_counter()
            self.lastTime = record.__dict__["created"]
            record.__dict__["msg"] = "S|" + msg
            ret = super().format(record)

        else:
            done = self.done_pattern.match(msg)
            if done:
                tag = done.groups()[0][1:] if len(done.groups()[0]) != 0 else "job"
                elapsed = time.perf_counter() - self.tag2time[tag] if tag in self.tag2time else -1.0
                ret = "      [{}] is done! ({:.4}s)".format(tag, elapsed) if tag in self.tag2time else "*LOG ERROR* ({} is not started[Done!]".format(tag)
                record.__dict__["msg"] = "D|" + ret
                ret = super().format(record)

            else:
                record.__dict__["msg"] = " |" + msg
                ret = super().format(record)


        return ret

def getLogger(name: str = __name__, logfile: str = None, logLevel: int = None) -> logging.Logger:

    isLoggerAlreadyExisted = False
    if name in logging.Logger.manager.loggerDict or name == "root": # loggerDict don't have root logger
        isLoggerAlreadyExisted = True
    elif logLevel == None:
        logLevel = logging.INFO # our default

    logger = logging.getLogger(name)
    if logLevel:
        logger.setLevel(logLevel)

    if not isLoggerAlreadyExisted:
        dqsh = DoneloggerStreamHandler(stream=sys.stdout) # setting stdout is needed for subprocess
        dqsh.setLevel(logLevel)
        dqlf = DoneloggerFormatter('%(asctime)s|%(levelname)s|%(message)s','%d/%m/%Y %H:%M:%S')
        dqsh.setFormatter(dqlf)
        logger.addHandler(dqsh)

        if logfile is not None:
            fh = RotatingFileHandler(logfile, maxBytes=1000000, backupCount=2, encoding='utf-8')
            fh.setLevel(logging.DEBUG)
            fh_formatter = logging.Formatter('%(asctime)s %(levelname)s %(filename)s %(name)s %(funcName)s %(message)s')
            fh.setFormatter(fh_formatter)
            logger.addHandler(fh)

    return logger

if __name__ == "__main__":


    logger = getLogger(__name__)
    logger.info("test")
    logger.warning("warn")
    logger.info("[Start] comment")
    time.sleep(1)
    logger.info("[Done] done message is ignored")
    logger.info("[Start:tag1]")
    logger.info("normal msg1")
    time.sleep(1)
    logger.info("[Done:tag1] ")
    logger.info("[Done:tag2] tag2 is not defined")
    logger.info("normal msg2")
    logger.info("normal msg3")
    logger.info("[Done:tag1] ")
    logger.info("normal msg4")
    logger.info("[Start] onece")
    logger.info("[Start] twice")
    time.sleep(1)
    logger.info("[Done]")
    logger.info("[Done] done nothing ")

    logger2 = getLogger("root", "log.log", logging.DEBUG)
    logger2.info("[Start] logger2 do something")
    time.sleep(1)
    logger2.info("[Done] done message")

    loggar3 = getLogger(__name__)
    logger.info("normal msg by logger3")

