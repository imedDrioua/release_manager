"""
Logging configuration for Release Management Application
File: utils/logging_config.py
"""

import logging
import logging.config
from pathlib import Path
from datetime import datetime

def setup_logging():
    """Setup logging configuration"""

    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Generate log filename with date
    log_filename = f"release_management_{datetime.now().strftime('%Y%m%d')}.log"
    log_path = log_dir / log_filename

    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            'detailed': {
                'format': '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'INFO',
                'formatter': 'standard',
                'stream': 'ext://sys.stdout'
            },
            'file': {
                'class': 'logging.FileHandler',
                'level': 'DEBUG',
                'formatter': 'detailed',
                'filename': str(log_path),
                'mode': 'a',
                'encoding': 'utf-8'
            },
            'error_file': {
                'class': 'logging.FileHandler',
                'level': 'ERROR',
                'formatter': 'detailed',
                'filename': str(log_dir / 'errors.log'),
                'mode': 'a',
                'encoding': 'utf-8'
            }
        },
        'loggers': {
            '': {  # root logger
                'handlers': ['console', 'file'],
                'level': 'INFO',
                'propagate': False
            },
            'release_management': {
                'handlers': ['console', 'file', 'error_file'],
                'level': 'DEBUG',
                'propagate': False
            },
            'database': {
                'handlers': ['file', 'error_file'],
                'level': 'DEBUG',
                'propagate': False
            },
            'jira': {
                'handlers': ['file', 'error_file'],
                'level': 'DEBUG',
                'propagate': False
            }
        }
    }

    logging.config.dictConfig(logging_config)

    # Test logging
    logger = logging.getLogger('release_management')
    logger.info("Logging system initialized")

    return logger

def get_logger(name):
    """Get a logger with the given name"""
    return logging.getLogger(f'release_management.{name}')