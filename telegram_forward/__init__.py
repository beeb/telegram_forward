try:
    from importlib.metadata import metadata, version  # type: ignore
except ModuleNotFoundError:
    from importlib_metadata import metadata, version  # type: ignore

__version__ = version('telegram_forward')
__doc__ = metadata('telegram_forward')['Summary']
__author__ = metadata('telegram_forward')['Author']

from .forward import *
