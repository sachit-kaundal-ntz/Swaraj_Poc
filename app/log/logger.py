import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Central logger configuration
def setup_logging():
    """Centralized logging configuration for the entire application"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    main_logger_name = "Invoice_log"
    log_file = log_dir / f"{main_logger_name}.log"
    
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(file_formatter)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    root_logger.propagate = False

def get_logger(name: str = None) -> logging.Logger:
    """
    Get a logger instance that inherits from the root configuration.
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)