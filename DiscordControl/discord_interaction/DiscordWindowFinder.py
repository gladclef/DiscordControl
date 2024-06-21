import ctypes

import dxcam
import numpy as np
import pywinauto
import screeninfo
from geometry import Pxy, Rect


class DiscordWindowFinder():
	""" Utility class to locate the discord window. """

	def __init__(self):
		self.dxcam_idx: int = 0
		self.camera: dxcam.DXCamera = None
		self.monitor_loc: Pxy = None

		self.get_camera_for_discord()
	
	def __del__(self):
		if self.camera is not None:
			try:
				self.camera.release()
			except Exception:
				pass
		self.camera = None
	
	def get_camera_for_discord(self):
		""" Chooses the camera application in which discord is currently visible. """
		# get the region of the continuous screen in which to find discord.
		reg: Rect = self._get_discord_region()

		# choose the monitor that contains the center pixel for discord
		target_pixel: Pxy = reg.top_left + Pxy(int(reg.width / 2), int(reg.height / 2))
		self.dxcam_idx, self.monitor_loc = self._get_matching_monitor_idx_loc(target_pixel)

		# setup the camera for the discord screen
		self.camera = dxcam.create(output_idx=self.dxcam_idx)
	
	def grab(self, reg: Rect = None) -> np.ndarray:
		# get the discord region, normalized to the discord monitor's location
		discord_reg = self._get_discord_region()
		discord_reg += self.monitor_loc

		# normalize input
		if reg is None:
			reg = discord_reg

		# restrict to the bounds of the discord monitor
		reg = reg.clip(0, self.camera.width, 0, self.camera.height)

		# grab the region
		ret = self.camera.grab(reg.to_ltrb())

		return ret

	@staticmethod
	def _get_window_region_from_name(name:str)-> Rect | None:
		hwnds = pywinauto.findwindows.find_windows(title_re=".*"+name+".*")
		if len(hwnds) == 0:
			return None
		if len(hwnds) > 1:
			print(f"Found more than one window matching name {name}")
			return None
		hwnd = hwnds[0]

		rect = ctypes.wintypes.RECT()
		ctypes.windll.user32.GetWindowRect(hwnd, ctypes.pointer(rect))
		return Rect.from_ltrb(rect.left, rect.top, rect.right, rect.bottom)

	@staticmethod
	def _get_discord_region() -> Rect:
		reg = DiscordWindowFinder._get_window_region_from_name('Discord')
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