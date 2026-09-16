from setuptools import setup

setup(
    name="OmniSight-Telemetry", # Nouveau nom unique pour débloquer PyPI
    version="1.0.0",
    author="Ilyas-The-Incredible-Dude",
    description="A lightweight real-time micro-telemetry flight recorder and behavioral monitoring framework.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com",
    py_modules=["OmniSight"], 
    install_requires=[
        "PyQt6",
        "watchdog",
        "psutil"
    ],
    entry_points={
        "console_scripts": [
            "omnisight=OmniSight:TelemetryPanel", # "OmniSight" avec le "i" majuscule
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.8',
)
