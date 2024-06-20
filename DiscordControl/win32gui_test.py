import ctypes
import os

import cv2
import dxcam
import numpy as np
import pywinauto
import screeninfo
from PIL import Image


class DiscordWindowFinder():
	def __init__(self):
		self.dxcam_idx = 0
		self.camera: dxcam.DXCamera = None
		self.monitor_xy: tuple[int, int] = None

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
		l, t, w, h = self._get_discord_region_xywh()

		# choose the monitor that contains the center pixel for discord
		target_pixel = l + int(w / 2), t + int(h / 2)
		self.dxcam_idx, mon_left, mon_top = self._get_monitor_idxlefttop_for_virtual_screen_location(target_pixel)
		self.monitor_xy = mon_left, mon_top

		# setup the camera for the discord screen
		self.camera = dxcam.create(output_idx=self.dxcam_idx)
	
	def grab(self, reg_xywh: tuple[int, int, int, int] = None) -> np.ndarray:
		# get the discord region, normalized to the discord monitor's location
		dx, dy, dw, dh = self._get_discord_region_xywh()
		dx += self.monitor_xy[0]
		dy += self.monitor_xy[1]

		# normalize input
		if reg_xywh is None:
			reg_xywh = dx, dy, dw, dh
		x, y, w, h = reg_xywh

		# restrict to the bounds of the discord monitor
		x = np.min([np.max([x, 0]), self.camera.width])
		y = np.min([np.max([y, 0]), self.camera.height])
		w = np.min([np.max([w, 0]), self.camera.width - x])
		h = np.min([np.max([h, 0]), self.camera.height - y])

		# convert to ltrb
		l = x
		t = y
		r = x + w
		b = y + h

		# grab the region
		ret = self.camera.grab((l, t, r, b))

		return ret

	def grab_user_images_slice(self) -> np.ndarray:
		x = 116 # user images are typically at x=116
		y = 0
		w = 50 # user images are very small
		h = self.camera.height

		slice = self.grab((x, y, w, h))

		return slice

	@staticmethod
	def _get_window_rect_from_name(name:str)-> tuple[int, int, int, int] | None:
		hwnds = pywinauto.findwindows.find_windows(title_re=".*"+name+".*")
		if len(hwnds) == 0:
			return None
		if len(hwnds) > 1:
			print(f"Found more than one window matching name {name}")
			return None
		hwnd = hwnds[0]

		rect = ctypes.wintypes.RECT()
		ctypes.windll.user32.GetWindowRect(hwnd, ctypes.pointer(rect))
		return (rect.left, rect.top, rect.right, rect.bottom)

	@staticmethod
	def _get_discord_region_xywh() -> tuple[int, int, int, int] | None:
		reg = DiscordWindowFinder._get_window_rect_from_name('Discord')
		if reg is None:
			raise RuntimeError("Failed to find window matching 'Discord'")
		l, t, r, b = reg

		return (l, t, r-l, b-t)

	@staticmethod
	def _get_monitor_idxlefttop_for_virtual_screen_location(screen_location: tuple[int, int]) -> tuple[int, int, int]:
		# get monitor working areas
		output_working_areas: list[tuple[int, int, int, int]] = []
		for i, monitor in enumerate(screeninfo.get_monitors()):
			output_working_areas.append((monitor.x, monitor.y, monitor.width, monitor.height))

		# choose the monitor that contains the center pixel for discord
		for i, area in enumerate(output_working_areas):
			wl, wt, wr, wb = area[0], area[1], area[0]+area[2], area[1]+area[3]
			if wl < screen_location[0] and wr > screen_location[0] and wt < screen_location[1] and wb > screen_location[1]:
				return i, wl, wt
		
		raise RuntimeError(f"Could not find monitor containing virtual screen location {screen_location}")


class UserImagesLocator():
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

	def find_user_images(self):
		slice = self.discord_frame_grabber.grab_user_images_slice()
		annotated_slice = slice.copy()

		for name_ext in self.user_images:
			user_image = self.user_images[name_ext]

			# Start by matching off the corner pixels
			w, h = user_image.shape[1], user_image.shape[0]
			sample_pixels = [(0, 0), (w-1, 0), (w-1, h-1), (0, h-1), (int(w/2), int(h/2))]
			matches: list[bool] = []
			for i, pixel in enumerate(sample_pixels):
				x, y = pixel
				shifted_slice = slice[y:slice.shape[0]-(h-y-1), x:slice.shape[1]-(w-x-1)]
				if i == 0:
					matches = shifted_slice == user_image[y, x]
				else:
					matches = np.logical_and(matches, shifted_slice == user_image[y, x])
			matching_coords = np.where(matches)

			# Search for exact matches to our approximate matches
			x_searches, y_searches = matching_coords[1].tolist(), matching_coords[0].tolist()
			match_xy = None
			for x, y in zip(x_searches, y_searches):
				if np.all(slice[y:y+h, x:x+w] == user_image):
					match_xy = x, y
					break
			if match_xy is None:
				continue

			# Step 2: Get the size of the template. This is the same size as the match.
			trows,tcols = user_image.shape[:2]

			# Step 3: Draw the rectangle on large_image
			annotated_slice = cv2.rectangle(annotated_slice, match_xy, (match_xy[0]+tcols,match_xy[1]+trows),(0,0,255),2)
		
		return annotated_slice


if __name__ == "__main__":
	user_images_dir = "C:/Users/gladc/OneDrive/Documents/3d prints/deej/software/pics/user_pics"

	grabber = DiscordWindowFinder()
	user_locator = UserImagesLocator(grabber, user_images_dir)
	annotated = user_locator.find_user_images()
	img = Image.fromarray(annotated)
	img.show()
