#!/bin/bash

uv run ruff check . --fix --unsafe-fixes --preview --show-fixes
