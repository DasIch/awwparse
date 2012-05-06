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
    install_requires=["six>=1.1.0"],
    extras_require={
        # Required to make HTTP requests e.g. when using
        # :class:`awwparse.Resource`.
        "http-support": ["requests>=0.12.0"]
    },
    classifiers=[
        "Environment :: Console",
        "Topic :: Software Development :: User Interfaces",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.0",
        "Programming Language :: Python :: 3.1",
        "Programming Language :: Python :: 3.2",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy"
    ]
)
