import os
import sys

import cv2
import numpy as np
from PIL import Image

sys.path.append(os.path.normpath(os.path.join(__file__, "..", "..")))
from discord_interaction.DiscordWindowFinder import DiscordWindowFinder
from discord_interaction.User import User
from geometry import Pxy, Rect


class LocatorUserImages():
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

	def grab_user_images_slice(self) -> tuple[np.ndarray, Pxy]:
		x = 116 # user images are typically at x=116
		y = 0
		w = 50 # user images are very small
		h = self.discord_frame_grabber.camera.height
		reg = Rect.from_xywh(x, y, w, h)

		slice = self.discord_frame_grabber.grab(reg)

		return slice, reg.top_left

	def locate_users_annotations(self) -> tuple[list[User], np.ndarray]:
		""" Locates user images within the discord window.
		
		Returns
		-------
		users: list[User]
			Each found user with a visible user image corresponding
			to one of images in self.user_images_dir.
		annotated_slice: np.ndarray
			An small annotated screenshot of discord with the user
			images highlighted.
		"""
		slice, window_offset = self.grab_user_images_slice()
		users: list[User] = []
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
			window_rel_match = match + window_offset
			users.append(User(os.path.join(self.user_images_dir, name_ext), window_rel_match))

			# Debugging: draw the rectangle on large_image
			magenta = (255,0,255)
			annotated_slice = cv2.rectangle(annotated_slice, match.top_left.astuple(), match.bottom_right.astuple(), magenta, thickness=2)
		
		return users, annotated_slice