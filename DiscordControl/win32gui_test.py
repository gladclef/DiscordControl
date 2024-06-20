import ctypes
import os

import cv2
import dxcam
import numpy as np
import pywinauto
import screeninfo
from PIL import Image


class Pxy():
	""" Represents a single point (typically a pixel). """
	def __init__(self, x: int , y: int):
		self.x = x
		self.y = y

	def clip(self, min_x: int, max_x: int, min_y: int, max_y: int) -> "Pxy":
		x = np.clip(self.x, min_x, max_x)
		y = np.clip(self.y, min_y, max_y)
		return Pxy(x, y)
	
	def astuple(self) -> tuple[int, int]:
		return (self.x, self.y)
	
	def __add__(self, other: "Pxy") -> "Pxy":
		return Pxy(self.x + other.x, self.y + other.y)
	
	def __sub__(self, other: "Pxy") -> "Pxy":
		return self + -1*other
	
	def __mul__(self, other: int) -> "Pxy":
		return Pxy(int(self.x * other), int(self.y * other))
	
	def __div__(self, other: int) -> "Pxy":
		return self * (1.0 / other)
	
	def __eq__(self, other: "Pxy") -> bool:
		return self.x == other.x and self.y == other.y
	
	def __repr__(self) -> str:
		return "{%d,%d}" % (self.x, self.y)


class Rect():
	""" Represents a rectangular region in screen coordinates
	(x positive to the right, y positive down). """
	def __init__(self, top_left: Pxy, bottom_right: Pxy):
		# validate the input
		if (top_left.x > bottom_right.x) or (top_left.y > bottom_right.y):
			raise ValueError(f"Top-left x/y must be less than bottom-right x/y, but tl={top_left} and br={bottom_right}")

		self.top_left = top_left
		self.bottom_right = bottom_right

	@classmethod
	def from_ltrb(cls: type["Rect"], left: int, top: int, right: int, bottom: int) -> "Rect":
		ret: "Rect" = cls(Pxy(left, top), Pxy(right, bottom))
		return ret

	@classmethod
	def from_xywh(cls: type["Rect"], x: int, y: int, width: int, height: int) -> "Rect":
		ret: "Rect" = cls(Pxy(x, y), Pxy(x+width, y+height))
		return ret
	
	@property
	def x(self) -> int:
		return self.top_left.x
	
	@property
	def y(self) -> int:
		return self.top_left.y
	
	@property
	def width(self) -> int:
		return self.bottom_right.x - self.top_left.x
	
	@property
	def height(self) -> int:
		return self.bottom_right.y - self.top_left.y

	def to_xywh(self) -> tuple[int, int, int, int]:
		return self.top_left.x, self.top_left.y, self.width, self.height
	
	def to_ltrb(self) -> tuple[int, int, int, int]:
		return self.top_left.x, self.top_left.y, self.bottom_right.x, self.bottom_right.y
	
	def contains(self, point: Pxy) -> bool:
		l, t, r, b = self.to_ltrb()
		if point.x >= l and point.x <= r and point.y >= t and point.y <= b:
			return True
		return False
	
	def clip(self, min_x: int, max_x: int, min_y: int, max_y: int) -> "Rect":
		top_left = self.top_left.clip(min_x, max_x, min_y, max_y)
		min_x2, min_y2 = np.max([min_x, top_left.x]), np.max([min_y, top_left.y])
		bottom_right = self.bottom_right.clip(min_x2, max_x, min_y2, max_y)
		return Rect(top_left, bottom_right)
	
	def get_corners_xy(self, zero_index = False) -> list[Pxy]:
		if zero_index:
			ret = [(self.x, self.y), (self.x+self.width-1, self.y), (self.x+self.width-1, self.y+self.height-1), (self.x, self.y+self.height-1)]
		else:
			ret = [(self.x, self.y), (self.x+self.width, self.y), (self.x+self.width, self.y+self.height), (self.x, self.y+self.height)]
		return [Pxy(x, y) for x, y in ret]
	
	def __add__(self, other: Pxy) -> "Rect":
		return Rect(self.top_left + other, self.bottom_right + other)
	
	def __repr__(self):
		return "Rect{x:%d,y:%d,w:%d,h:%d}" % (self.x, self.y, self.width, self.height)


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


class UserImagesLocator():
	""" Locates user images within the discord window. """

	def __init__(self, discord_frame_grabber: DiscordWindowFinder, user_images_dir: str):
		self.discord_frame_grabber = discord_frame_grabber
		self.user_images_dir = user_images_dir
		self.user_images: dict[str, np.ndarray] = None
		""" Dict of file names+ext (no path) to the loaded and pre-processed image """

		# populate the user_images
		self.load_user_images()

	@staticmethod
	def _load_images_from_dir(images_dir: str) -> dict[str, np.ndarray]:
		contents = os.listdir(images_dir)
		contents = [os.path.join(images_dir, f) for f in contents]
		files = list(filter(lambda f: os.path.isfile(f), contents))
		image_files = list(filter(lambda f: f.endswith(".png"), files))

		ret: dict[str, np.ndarray] = {}
		for f in image_files:
			img = Image.open(f)
			ret[f] = np.array(img)

		return ret

	def load_user_images(self) -> list[np.ndarray]:
		if self.user_images is not None:
			return self.user_images
		
		images_from_dir = self._load_images_from_dir(self.user_images_dir)
		
		self.user_images = {}
		for path_name_ext in images_from_dir:
			name_ext = os.path.basename(path_name_ext)
			square_image = images_from_dir[path_name_ext][6:18, 6:18, :3]
			self.user_images[name_ext] = square_image

		return self.user_images

	def grab_user_images_slice(self) -> np.ndarray:
		x = 116 # user images are typically at x=116
		y = 0
		w = 50 # user images are very small
		h = self.discord_frame_grabber.camera.height
		reg = Rect.from_xywh(x, y, w, h)

		slice = self.discord_frame_grabber.grab(reg)

		return slice

	def locate_names_regions_annotations(self) -> tuple[dict[str, Rect], np.ndarray]:
		""" Locates user images within the discord window.
		
		Returns
		-------
		names_to_regions: dict[str, Rect]
			The rectangular region for each found user image, in
			screen coordinates relative to the discord window.
		annotated_slice: np.ndarray
			An small annotated screenshot of discord with the user
			images highlighted.
		"""
		slice = self.discord_frame_grabber.grab_user_images_slice()
		user_images_regions: dict[str, Rect] = {}
		annotated_slice = slice.copy()

		for name_ext in self.user_images:
			user_image = self.user_images[name_ext]

			# Start by matching off the corner pixels (and center pixel).
			# We do this for speed, since np.where and np.logical_and are much
			# faster than scanning through the entire slice for the user image.
			w, h = user_image.shape[1], user_image.shape[0]
			sample_pixels = Rect.from_xywh(0, 0, w, h).get_corners_xy(True)
			sample_pixels.append(Pxy(int(w/2), int(h/2)))
			matches: list[bool] = []
			for i, pixel in enumerate(sample_pixels):
				shifted_slice = slice[pixel.y:slice.shape[0]-(h-pixel.y-1), pixel.x:slice.shape[1]-(w-pixel.x-1)]
				if i == 0:
					matches = shifted_slice == user_image[pixel.y, pixel.x]
				else:
					matches = np.logical_and(matches, shifted_slice == user_image[pixel.y, pixel.x])
			matching_coords = np.where(matches)

			# Search for exact matches to our approximate matches
			x_searches, y_searches = matching_coords[1].tolist(), matching_coords[0].tolist()
			match: Rect = None
			for x, y in zip(x_searches, y_searches):
				if x+w <= slice.shape[1] and y+h <= slice.shape[0]:
					if np.all(slice[y:y+h, x:x+w] == user_image):
						match = Rect.from_xywh(x, y, w, h)
						break
			if match is None:
				continue

			# Add the match to our return value
			user_images_regions[name_ext] = match

			# Debugging: draw the rectangle on large_image
			magenta = (255,0,255)
			annotated_slice = cv2.rectangle(annotated_slice, match.top_left.astuple(), match.bottom_right.astuple(), magenta, thickness=2)
		
		return user_images_regions, annotated_slice


if __name__ == "__main__":
	user_images_dir = "C:/Users/gladc/OneDrive/Documents/3d prints/deej/software/pics/user_pics"

	grabber = DiscordWindowFinder()
	user_locator = UserImagesLocator(grabber, user_images_dir)
	user_images_regions, annotated = user_locator.locate_name_region_annotations()
	for name in user_images_regions:
		print(f"{name}: {user_images_regions[name]}")
	img = Image.fromarray(annotated)
	img.show()
