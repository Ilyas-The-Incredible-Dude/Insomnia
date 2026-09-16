from setuptools import setup

setup(
    name="OmniSight",
    version="1.0.0",
    author="Ilyas-The-Incredible-Dude",
    description="A lightweight real-time micro-telemetry flight recorder and behavioral monitoring framework.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com",
    py_modules=["OmniSight"], # Indique à Python que le script est directement à la racine
    install_requires=[
        "PyQt6",
        "watchdog",
        "psutil"
    ],
    entry_points={
        "console_scripts": [
            "omnisight=OmnSight:TelemetryPanel", # Correction du point d'entrée pour lancer la fenêtre
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.8',
)
