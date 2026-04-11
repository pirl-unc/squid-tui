from importlib.metadata import version, PackageNotFoundError


from .app import SquidApp, run

try:
    __version__ = version("squid-tui")
except PackageNotFoundError:
    __version__ = "unknown"
