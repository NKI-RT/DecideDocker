"""Logger Module."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Union

from decide.paths import LOG_DIR


def setup_logger(
    name: Optional[Union[str, Path]] = None,
    log_file: Union[str, Path] = None,
    level: str = logging.DEBUG,
    *,
    log_to_console=True,
) -> logging.Logger:
    """SetUp the Logger.

    :param Optional[Union[str, Path]] name: Logger Name, defaults to None
    :param Union[str, Path] log_file: Log file, defaults to None
    :param str level: Logging Level, defaults to logging.DEBUG
    :param bool log_to_console: Log to Console?, defaults to True
    :return logging.Logger: The logger Object.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        formatter = logging.Formatter("[ %(asctime)s - %(name)s ] - %(levelname)s : %(message)s")

        if log_to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        if log_file:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(str(log_file), maxBytes=5_000_000, backupCount=5)
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    return logger


logger = setup_logger("DECIDE", LOG_DIR / "decide.log")
