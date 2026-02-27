#!/usr/bin/env python3
"""
Modified version for CLESSN group library
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from research import *
import json

# Override zotero config to use group
def get_zotero_group_config():
    config_path = os.path.expanduser("~/.openclaw/workspace/.zotero-config.json")
    with open(config_path) as f:
        config = json.load(f)
    return config

if __name__ == "__main__":
    # Same CLI but use group library
    main()
