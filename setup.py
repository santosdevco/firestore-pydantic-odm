from setuptools import setup, find_packages
from pathlib import Path

# Leer el contenido del README.rst
this_directory = Path(__file__).parent
long_description = (this_directory / "README.rst").read_text(encoding='utf-8')

setup(
    name="firestore_pydantic_odm",
    version="0.1.3",
    description="ODM para Firestore utilizando Pydantic y operaciones asíncronas",
    long_description=long_description,
    long_description_content_type='text/x-rst',
    author="Santos Dev Co",
    author_email="projects@santosdevco.com",
    url="https://github.com/santosdevco/firestore_pydantic_odm",
    packages=find_packages(),
    install_requires=[
        "pydantic",
        "google-cloud-firestore>=2.0.0",
        # otras dependencias necesarias
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    keywords="firestore pydantic odm asynchronous",
    project_urls={
        "Bug Tracker": "https://github.com/santosdevco/firestore_pydantic_odm/issues",
        "Documentation": "https://github.com/santosdevco/firestore_pydantic_odm#readme",
        "Source Code": "https://github.com/santosdevco/firestore_pydantic_odm",
    },
)
