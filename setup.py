# setup.py
from setuptools import setup, find_packages

setup(
    name="firestore_pydantic_odm",
    version="0.1.0",
    description="ODM para Firestore utilizando Pydantic y operaciones asíncronas",
    author="Santos Dev Co",
    author_email="projects@santosdevco.com",
    packages=find_packages(), 
    install_requires=[
        "pydantic",
        "google-cloud-firestore>=2.0.0",
        # otras dependencias necesarias
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)
