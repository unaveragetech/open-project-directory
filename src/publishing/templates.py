"""Jinja2 template loading for page generation."""
import os
from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "templates")


def get_environment(templates_dir=None):
    env = Environment(
        loader=FileSystemLoader(templates_dir or TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env
