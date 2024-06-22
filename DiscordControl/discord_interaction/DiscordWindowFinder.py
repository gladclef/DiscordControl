import ctypes
import os
import sys
import time

import dxcam
import numpy as np
import pywinauto
import screeninfo
from geometry import Pxy, Rect
from PIL import ImageGrab

sys.path.append(os.path.normpath(os.path.join(__file__, "..", "..")))
from Fresh import Fresh


class DiscordWindowFinder():
    """ Utility class to locate the discord window. """

    def __init__(self):
        self.dxcam_idx: int = 0
        self.camera: dxcam.DXCamera = None
        self.monitor_loc: Pxy = None
        self.hwnd = Fresh(self._get_discord_window_handle)

        self._get_camera_for_discord()
    
    def __del__(self):
        if self.camera is not None:
            try:
                self.camera.release()
            except Exception:
                pass
        self.camera = None

    @property
    def width(self):
        return self._get_window_region().width

    @property
    def height(self):
        return self._get_window_region().height
    
    def _get_camera_for_discord(self):
        """ Chooses the camera application in which discord is currently visible. """
        # get the region of the continuous screen in which to find discord.
        reg: Rect = self._get_discord_region()

        # choose the monitor that contains the center pixel for discord
        target_pixel: Pxy = reg.top_left + Pxy(int(reg.width / 2), int(reg.height / 2))
        self.dxcam_idx, self.monitor_loc = self._get_matching_monitor_idx_loc(target_pixel)

        # setup the camera for the discord screen
        self.camera = dxcam.create(output_idx=self.dxcam_idx)
    
    def does_window_exist(self):
        return self.hwnd.get() != None

    def activate_window(self):
        user32 = ctypes.windll.user32
        user32.SetForegroundWindow(self.hwnd.get())
        if user32.IsIconic(self.hwnd.get()):
            user32.ShowWindow(self.hwnd.get(), 9)
    
    def grab(self, reg: Rect = None) -> np.ndarray:
        """ Grabs an image from the screen, relative to Discord's window """
        # get the discord region, normalized to the discord monitor's location
        discord_reg = self._get_discord_region()
        discord_reg -= self.monitor_loc
        tl_corner = discord_reg.top_left.clip(0, self.camera.width, 0, self.camera.height)

        # normalize input
        if reg is None:
            reg = Rect.from_xywh(discord_reg.x, discord_reg.y, discord_reg.width, discord_reg.height)
        reg += tl_corner

        # restrict to the bounds of the discord window
        reg = reg.clip(0, tl_corner.x + discord_reg.width, 0, tl_corner.y + discord_reg.height)

        # restrict to the bounds of the discord monitor
        reg = reg.clip(0, self.camera.width, 0, self.camera.height)

        # grab the region
        ret = self.camera.grab(reg.to_ltrb())
        if ret is None:
            # DXcam only seems to work when the screen is being actively redrawn,
            # fall back on Pillow.
            ret_img = ImageGrab.grab((reg + self.monitor_loc).to_ltrb(), all_screens=True)
            ret = np.array(ret_img)

        return ret
    
    def window_corner(self, corner='tl') -> Pxy:
        """ Get the corner of the discord window, in virtual screen coordinates """
        corners = self._get_window_region().get_corners_xy()

        if corner == 'tl':
            return corners[0]
        elif corner == 'tr':
            return corners[1]
        elif corner == 'br':
            return corners[2]
        elif corner == 'bl':
            return corners[3]
    
    def virtual_coord(self, coord: Pxy, rel='tl') -> Pxy:
        """ Get the virtual screen space coordinate for
        the given discord window coordinate. """
        return self.window_corner(rel) + coord

    @staticmethod
    def _get_discord_window_handle():
        hwnds = pywinauto.findwindows.find_windows(title_re=".*- Discord")
        if len(hwnds) == 0:
            return None
        if len(hwnds) > 1:
            print(f"Found more than one window matching name 'Discord'")
            return None
        hwnd = hwnds[0]

        return hwnd

    def _get_window_region(self) -> Rect | None:
        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(self.hwnd.get(), ctypes.pointer(rect))
        return Rect.from_ltrb(rect.left, rect.top, rect.right, rect.bottom)

    def _get_discord_region(self) -> Rect:
        reg = self._get_window_region()
        if reg is None:
            raise RuntimeError("Failed to find window matching 'Discord'")
        return reg

    @staticmethod
    def _get_matching_monitor_idx_loc(screen_location: Pxy) -> tuple[int, Pxy]:
        # get monitor working areas
        output_working_areas: list[Rect] = []
        for i, monitor in enumerate(screeninfo.get_monitors()):
            output_working_areas.append(Rect.from_xywh(monitor.x, monitor.y, monitor.width, monitor.height))

        # choose the monitor that contains the center pixel for discord
        for i, area in enumerate(output_working_areas):
            if area.contains(screen_location):
                return i, area.top_left
        
        raise RuntimeError(f"Could not find a monitor containing virtual screen location {screen_location}")