# coding: utf-8
from setuptools import setup


setup(
    name="Awwparse",
    version="0.1-dev",
    description="A parser for command line arguments",
    url="http://github.com/DasIch/awwparse",
    license="BSD",
    author="Daniel Neuhäuser",
    author_email="dasdasich@gmail.com",
    packages=[
        "awwparse",
        "awwparse.testsuite"
    ],
    zip_safe=False,
    platforms="any",
    install_requires=["six>=1.1.0"]
)
