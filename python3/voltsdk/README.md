# voltsdk

Python SDK for interacting with the Volt API.

## Installation

```bash
pip install voltsdk
```

Install visualization support with:

```bash
pip install "voltsdk[visualization]"
```

Install notebook support with:

```bash
pip install "voltsdk[notebook]"
```

## Usage

```python
from voltsdk import VoltClient

client = VoltClient(
    secret_key="your-secret-key",
    base_url="https://api.example.com"
)
```

