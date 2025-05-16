"""
具体截图方法实现模块。
包含各种截图方法的具体实现。
"""

import cv2
import numpy as np
from datetime import datetime
from typing import Optional

from module.device.screenshot.base import ScreenshotMethod
from module.device.method.adb import Adb
from module.device.method.ascreencap import AScreenCap
from module.device.method.droidcast import DroidCast
from module.device.method.scrcpy import Scrcpy
from module.device.method.nemu_ipc import NemuIpc
from module.device.method.ldopengl import LDOpenGL
from module.base.logger import logger


class AdbScreenshot(ScreenshotMethod):
    """ADB截图方法"""
    
    def __init__(self, adb: Adb):
        self.adb = adb
    
    def is_available(self) -> bool:
        return True
    
    def screenshot(self) -> np.ndarray:
        return self.adb.screenshot_adb()
    
    def get_name(self) -> str:
        return 'ADB'


class AScreenCapScreenshot(ScreenshotMethod):
    """aScreenCap截图方法"""
    
    def __init__(self, ascreencap: AScreenCap):
        self.ascreencap = ascreencap
    
    def is_available(self) -> bool:
        return self.ascreencap.ascreencap_available()
    
    def screenshot(self) -> np.ndarray:
        return self.ascreencap.screenshot_ascreencap()
    
    def get_name(self) -> str:
        return 'aScreenCap'


class DroidCastScreenshot(ScreenshotMethod):
    """DroidCast截图方法"""
    
    def __init__(self, droidcast: DroidCast):
        self.droidcast = droidcast
    
    def is_available(self) -> bool:
        return self.droidcast.droidcast_available()
    
    def screenshot(self) -> np.ndarray:
        return self.droidcast.screenshot_droidcast()
    
    def get_name(self) -> str:
        return 'DroidCast'


class ScrcpyScreenshot(ScreenshotMethod):
    """scrcpy截图方法"""
    
    def __init__(self, scrcpy: Scrcpy):
        self.scrcpy = scrcpy
    
    def is_available(self) -> bool:
        return self.scrcpy.scrcpy_available()
    
    def screenshot(self) -> np.ndarray:
        return self.scrcpy.screenshot_scrcpy()
    
    def get_name(self) -> str:
        return 'scrcpy'


class NemuIpcScreenshot(ScreenshotMethod):
    """Nemu IPC截图方法"""
    
    def __init__(self, nemu_ipc: NemuIpc):
        self.nemu_ipc = nemu_ipc
    
    def is_available(self) -> bool:
        return self.nemu_ipc.nemu_ipc_available()
    
    def screenshot(self) -> np.ndarray:
        return self.nemu_ipc.screenshot_nemu_ipc()
    
    def get_name(self) -> str:
        return 'nemu_ipc'


class LDOpenGLScreenshot(ScreenshotMethod):
    """LD OpenGL截图方法"""
    
    def __init__(self, ldopengl: LDOpenGL):
        self.ldopengl = ldopengl
    
    def is_available(self) -> bool:
        return self.ldopengl.ldopengl_available()
    
    def screenshot(self) -> np.ndarray:
        return self.ldopengl.screenshot_ldopengl()
    
    def get_name(self) -> str:
        return 'ldopengl' 