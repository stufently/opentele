from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__ = _pkg_version("opentele-ng")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

from . import td, tl

__all__ = ["td", "tl", "__version__"]
