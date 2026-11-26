#!/usr/bin/env python3
"""Convenience entrypoint: python scripts/generate_site.py [--data ...] [--out ...]"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.publishing.generator import main

if __name__ == "__main__":
    sys.exit(main())
