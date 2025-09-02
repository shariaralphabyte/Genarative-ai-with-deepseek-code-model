"""
Utility functions for training pipeline
"""

import os
import json
import logging
import yaml
from typing import Dict, Any

def setup_logging(level: str = "INFO"):
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('training.log'),
            logging.StreamHandler()
        ]
    )

def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML or JSON file"""
    with open(config_path, 'r') as f:
        if config_path.endswith('.yaml') or config_path.endswith('.yml'):
            return yaml.safe_load(f)
        else:
            return json.load(f)

def save_config(config: Dict[str, Any], path: str):
    """Save configuration to file"""
    with open(path, 'w') as f:
        if path.endswith('.yaml') or path.endswith('.yml'):
            yaml.dump(config, f, default_flow_style=False)
        else:
            json.dump(config, f, indent=2)
