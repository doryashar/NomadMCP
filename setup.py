"""Setup script for NomadMCP."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="nomad-mcp",
    version="0.1.0",
    author="NomadMCP",
    author_email="nomad@example.com",
    description="MCP server for automated task execution using CodeNomad/OpenCode",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/doryashar/NomadMCP",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=[
        "mcp>=0.9.0",
        "httpx>=0.27.0",
        "gitpython>=3.1.0",
        "pydantic>=2.0.0",
    ],
    entry_points={
        "console_scripts": [
            "nomad-mcp=src.server:main",
        ],
    },
)
