import os
import struct
import typing
from typing import Optional

from .. import exception as excpt
from ..api import API, APIData
from . import configs
from .account import Account, MapData, StorageAccount
from .auth import AuthKey, AuthKeyType
from .mtp import MTP
from .storage import Serialize, Storage
from .tdesktop import TDesktop
