from setuptools import setup, find_packages

setup(
    name="OmniSight",
    version="1.0.0",
    author="YourName",
    description="A lightweight real-time micro-telemetry flight recorder and behavioral monitoring framework.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="MET_LE_LIEN_DE_TON_GITHUB_ICI",
    packages=find_packages(),
    install_requires=[
        "PyQt6",
        "watchdog",
        "psutil"
    ],
    entry_points={
        "console_scripts": [
            "omnisight=omnisight.app:main", # Permet de lancer l'app juste en tapant "omnisight" dans un terminal
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.8',
)
