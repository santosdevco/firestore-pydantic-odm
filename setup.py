from pathlib import Path
from setuptools import setup, find_packages

ROOT = Path(__file__).parent
README = (ROOT / "README.md").read_text(encoding="utf-8")  # markdown is more common

setup(
    name="firestore_pydantic_odm",
    version="0.2.3",
    description="Asynchronous Pydantic ODM for Google Cloud Firestore",
    long_description=README,
    long_description_content_type="text/markdown",
    author="Santos Dev Co",
    author_email="projects@santosdevco.com",
    url="https://github.com/santosdevco/firestore-pydantic-odm",
    license="MIT",
    license_files=["LICENSE"],
    packages=find_packages(exclude=("tests",)),
    include_package_data=True,           # include py.typed
    package_data={"firestore_pydantic_odm": ["py.typed"]},
    python_requires=">=3.8",
    install_requires=[
        "pydantic>=1.5,<3.0.0",
        "google-cloud-firestore>=2.0.0",  # recent async fixes
    ],
    extras_require={
        "emulator": ["google-cloud-firestore-emulator"],
        "dev": ["black", "ruff", "pytest", "pytest-asyncio"],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Framework :: AsyncIO",
        "Topic :: Database :: Front-Ends",
        "Typing :: Typed",
    ],
    keywords=[
        "firestore",
        "pydantic",
        "odm",
        "asyncio",
        "google cloud",
    ],
    project_urls={
        "Documentation": "https://github.com/santosdevco/firestore-pydantic-odm#readme",
        "Changelog": "https://github.com/santosdevco/firestore-pydantic-odm/releases",
        "Issue Tracker": "https://github.com/santosdevco/firestore-pydantic-odm/issues",
        "Source Code": "https://github.com/santosdevco/firestore-pydantic-odm",
    },
)
