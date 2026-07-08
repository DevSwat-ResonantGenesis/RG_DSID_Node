"""
Production Entry Point for ResonantGenesis Node API Server.

This module provides a production-ready entry point with:
- Environment-based configuration
- Structured logging
- Security headers
- Graceful shutdown handling
- Health monitoring

Usage: python -m resonant_node.api
"""

import os
import sys
import signal
import logging
from typing import Optional

import uvicorn
from uvicorn.config import LOGGING_CONFIG

from .server import APIServer


# Configure structured logging
def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure production logging with structured format."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )
    
    # Suppress noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    return logging.getLogger("resonant_node")


# Environment configuration with secure defaults
class NodeConfig:
    """Production configuration from environment variables."""
    
    def __init__(self):
        self.host: str = os.getenv("NODE_HOST", "0.0.0.0")
        self.port: int = int(os.getenv("NODE_PORT", "8081"))
        self.workers: int = int(os.getenv("NODE_WORKERS", "1"))
        self.log_level: str = os.getenv("NODE_LOG_LEVEL", "INFO")
        self.env: str = os.getenv("NODE_ENV", "production")
        
        # Security settings
        self.allowed_origins: list = os.getenv(
            "NODE_ALLOWED_ORIGINS", 
            "https://dev-swat.com,https://www.dev-swat.com,https://api.dev-swat.com"
        ).split(",")
        
        # Rate limiting
        self.rate_limit_requests: int = int(os.getenv("NODE_RATE_LIMIT", "100"))
        self.rate_limit_window: int = int(os.getenv("NODE_RATE_LIMIT_WINDOW", "60"))
        
        # Timeouts
        self.request_timeout: int = int(os.getenv("NODE_REQUEST_TIMEOUT", "30"))
        self.keepalive_timeout: int = int(os.getenv("NODE_KEEPALIVE_TIMEOUT", "5"))
    
    def validate(self) -> bool:
        """Validate configuration."""
        if self.port < 1 or self.port > 65535:
            raise ValueError(f"Invalid port: {self.port}")
        if self.workers < 1:
            raise ValueError(f"Invalid workers count: {self.workers}")
        return True


# Graceful shutdown handler
class GracefulShutdown:
    """Handle graceful shutdown signals."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.shutdown_requested = False
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True


def main():
    """
    Production entry point for the Node API server.
    
    Initializes logging, validates configuration, and starts the server
    with production-ready settings.
    """
    # Load and validate configuration
    config = NodeConfig()
    config.validate()
    
    # Setup logging
    logger = setup_logging(config.log_level)
    logger.info(f"Starting ResonantGenesis Node API Server")
    logger.info(f"Environment: {config.env}")
    logger.info(f"Host: {config.host}:{config.port}")
    logger.info(f"Workers: {config.workers}")
    
    # Initialize graceful shutdown handler
    shutdown_handler = GracefulShutdown(logger)
    
    # Create API server with security settings
    server = APIServer(
        host=config.host,
        port=config.port,
    )
    
    # Configure uvicorn with production settings
    uvicorn_config = {
        "host": config.host,
        "port": config.port,
        "log_level": config.log_level.lower(),
        "access_log": config.env != "production",  # Disable access logs in production
        "timeout_keep_alive": config.keepalive_timeout,
        "limit_concurrency": 1000,
        "limit_max_requests": 10000,
    }
    
    # Add SSL if certificates are provided
    ssl_keyfile = os.getenv("NODE_SSL_KEYFILE")
    ssl_certfile = os.getenv("NODE_SSL_CERTFILE")
    if ssl_keyfile and ssl_certfile:
        uvicorn_config["ssl_keyfile"] = ssl_keyfile
        uvicorn_config["ssl_certfile"] = ssl_certfile
        logger.info("SSL enabled")
    
    try:
        logger.info("Server starting...")
        uvicorn.run(server._app, **uvicorn_config)
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
    finally:
        logger.info("Server shutdown complete")


if __name__ == "__main__":
    main()
