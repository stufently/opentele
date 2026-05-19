import pathlib
from setuptools import setup

README = (pathlib.Path(__file__).parent / "README.md").read_text(encoding="utf-8")

PACKAGE_NAME = "opentele"
DIST_NAME = "opentele-ng"
VERSION = "0.4.0"
SOURCE_DIRECTORY = "src"

with open("requirements.txt", encoding="utf-8") as data:
    requirements = [
        line for line in data.read().split("\n") if line and not line.startswith("#")
    ]

setup(
    name=DIST_NAME,
    version=VERSION,
    license="MIT",
    description=(
        "opentele-ng — modern fork of opentele for Python 3.10-3.13 "
        "(3.14 experimental). Convert Telegram Desktop tdata to Telethon "
        "sessions; supports current Telegram Desktop 5.x-6.x tdata format "
        "with new lskType keys (RoundPlaceholder, InlineBotsDownloads, "
        "MediaLastPlaybackPositions, BotStorages as Dict[PeerId,FileKey], Prefs)."
    ),
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/stufently/opentele",
    author="stufently (fork of thedemons)",
    author_email="vitya5503@gmail.com",
    python_requires=">=3.10",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: MacOS",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
        "Development Status :: 4 - Beta",
        "Topic :: Communications :: Chat",
    ],
    keywords=[
        "tdata",
        "tdesktop",
        "telegram",
        "telegram-desktop",
        "telethon",
        "opentele",
        "opentele-ng",
        "python-3.13",
        "python-3.14",
    ],
    include_package_data=True,
    packages=[PACKAGE_NAME, PACKAGE_NAME + ".td", PACKAGE_NAME + ".tl"],
    package_dir={PACKAGE_NAME: SOURCE_DIRECTORY},
    install_requires=requirements,
)
