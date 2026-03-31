"""
logging_config.py — Centralized logging setup.

Provides a unified logger configuration for the entire application,
ensuring consistent formatting and level enforcement.
"""
import logging
import sys
from typing import logging as LoggingModuleType

def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured logger instance for the given module name.
    
    Args:
        name (str): The name of the logger, typically `__name__` of the calling module.
        
    Returns:
        logging.Logger: The configured Logger instance.
    """
    logger: logging.Logger = logging.getLogger(name)
    if not logger.handlers:
        handler: logging.StreamHandler = logging.StreamHandler(sys.stdout)
        formatter: logging.Formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
