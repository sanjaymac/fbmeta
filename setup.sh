#!/bin/bash
# Install playwright and its dependencies
pip install playwright

# Install required browsers
playwright install --with-deps
