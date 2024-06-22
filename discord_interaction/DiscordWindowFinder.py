import ctypes
import os
import sys

import numpy as np
import pywinauto
import screeninfo
from geometry import Pxy, Rect
from PIL import ImageGrab

sys.path.append(os.path.normpath(os.path.join(__file__, "..", "..")))


class DiscordWindowFinder():
    """ Utility class to locate the discord window. """

    def __init__(self):
        self.monitor_idx: int = 0
        self.monitor_area: Rect = None
        self.discord_handle: int = None
        self.last_discord_reg: Rect = None

        self._update_window_for_discord()

    @property
    def width(self):
        return self._get_window_region().width

    @property
    def height(self):
        return self._get_window_region().height
    
    def _update_window_for_discord(self, discord_reg: Rect = None):
        """ Chooses the window in which discord is currently visible. """
        # get the region of the continuous screen in which to find discord.
        if discord_reg is None:
            discord_reg = self._get_discord_region()

        # Assume that if the discord location hasn't changed,
        # then the window hasn't changed.
        if discord_reg == self.last_discord_reg:
            return
        self.last_discord_reg = discord_reg

        # choose the monitor that contains the center pixel for discord
        middle_pixel = Pxy(int(discord_reg.width / 2), int(discord_reg.height / 2))
        target_pixel: Pxy = discord_reg.top_left + middle_pixel
        monitor_idx, monitor_area = self._get_matching_monitor_idx_area(target_pixel)

        # set internal values
        if monitor_idx != self.monitor_idx:
            print(f"New monitor: {monitor_idx}")
            self.monitor_idx, self.monitor_area = monitor_idx, monitor_area
    
    def does_window_exist(self):
        hwnd = self.discord_handle
        user32 = ctypes.windll.user32
        return user32.IsWindow(hwnd)

    def activate_window(self):
        hwnd = self.get_discord_window_handle()
        user32 = ctypes.windll.user32
        user32.SetForegroundWindow(hwnd)
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)
    
    def _grab(self, reg: Rect = None) -> np.ndarray:
        # get the discord location
        discord_reg = self._get_discord_region()

        # get the latest monitor index and region
        self._update_window_for_discord(discord_reg)

        # normalize the discord region to the discord monitor's location
        discord_reg -= self.monitor_area.top_left
        tl_corner = discord_reg.top_left.clip(0, self.monitor_area.width, 0, self.monitor_area.height)

        # normalize input
        if reg is None:
            reg = Rect.from_xywh(discord_reg.x, discord_reg.y, discord_reg.width, discord_reg.height)
        reg += tl_corner

        # restrict to the bounds of the discord window
        reg = reg.clip(0, tl_corner.x + discord_reg.width, 0, tl_corner.y + discord_reg.height)

        # restrict to the bounds of the discord monitor
        reg = reg.clip(0, self.monitor_area.width, 0, self.monitor_area.height)

        # grab the region
        ret_img = ImageGrab.grab((reg + self.monitor_area.top_left).to_ltrb(), all_screens=True)
        ret = np.array(ret_img)
        
        return ret
    
    def grab(self, reg: Rect = None) -> np.ndarray:
        """ Grabs an image from the screen, relative to Discord's window """
        return self._grab(reg)
    
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

    def get_discord_window_handle(self):
        if self.discord_handle is not None:
            if self.does_window_exist():
                return self.discord_handle
            else:
                pass # continue to retrieve the window handle

        hwnds = pywinauto.findwindows.find_windows(title_re=".*- Discord")
        if len(hwnds) == 0:
            return None
        if len(hwnds) > 1:
            print(f"Found more than one window matching name 'Discord'")
            return None
        hwnd = hwnds[0]

        self.discord_handle = hwnd
        return self.discord_handle

    def _get_window_region(self) -> Rect | None:
        hwnd = self.get_discord_window_handle()
        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.pointer(rect))
        return Rect.from_ltrb(rect.left, rect.top, rect.right, rect.bottom)

    def _get_discord_region(self) -> Rect:
        reg = self._get_window_region()
        if reg is None:
            raise RuntimeError("Failed to find window matching 'Discord'")
        return reg

    @staticmethod
    def _get_matching_monitor_idx_area(screen_location: Pxy) -> tuple[int, Pxy]:
        """ Finds the monitor that contains the given virtual screen pixel.

        Parameters
        ----------
        screen_location : Pxy
            The virtual screen pixel to find a matching monitor for.

        Returns
        -------
        monitor_idx: int
            The index of the monitor that contains the screen location.
        monitor_area: Rect
            The monitor's area on the virtual screen.

        Raises
        ------
        RuntimeError
            IF the given screen_location isn't located within any of the found monitors
        """        
        # get monitor working areas
        output_working_areas: list[Rect] = []
        for i, monitor in enumerate(screeninfo.get_monitors()):
            output_working_areas.append(Rect.from_xywh(monitor.x, monitor.y, monitor.width, monitor.height))

        # choose the monitor that contains the center pixel for discord
        for i, area in enumerate(output_working_areas):
            if area.contains(screen_location):
                return i, area
        
        raise RuntimeError(f"Could not find a monitor containing virtual screen location {screen_location}")