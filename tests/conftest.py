import pytest_asyncio
import pytest
pytest_plugins = "pytest_asyncio"
pytest_asyncio.plugin.DEFAULT_FIXTURE_LOOP_SCOPE = "function"
