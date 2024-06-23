import copy
import os
import sys

import cv2
import numpy as np
from PIL import Image

sys.path.append(os.path.normpath(os.path.join(__file__, "..", "..")))
from discord_interaction.DiscordWindowFinder import DiscordWindowFinder
from discord_interaction.User import UpdateStatus as UserUpdateStatus
from discord_interaction.User import User
from geometry import Pxy, Rect


class LocatorUserImages():
    """ Locates user images within the discord window. """

    def __init__(self, discord_frame_grabber: DiscordWindowFinder, user_images_dir: str):
        self.discord_frame_grabber = discord_frame_grabber
        self.user_images_dir = user_images_dir
        self.users: list[User] = []
        """ Dict of file names+ext (no path) to the loaded and pre-processed image """

        # populate the users
        self.load_users_as_necessary()

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

    def load_users_as_necessary(self) -> list[User]:
        # get a list of already loaded user images
        already_loaded: set[str] = {user.voice_icon_path_name_ext for user in self.users}
        
        # load any new images
        images_from_dir = self._load_images_from_dir(self.user_images_dir)
        for path_name_ext in images_from_dir:
            if path_name_ext not in already_loaded:
                self.users.append(User(path_name_ext))

        return self.users
    
    def check_user_images_files(self):
        """ Checks for new (or stale) user image files and reloads or unloads them, as necessary. """
        # check for any users that need to be reloaded or unloaded
        for user in copy.copy(self.users):
            update_status = user.update_as_necessary()
            if update_status == UserUpdateStatus.unloaded:
                self.users.remove(user)
        
        # check for any image files that don't yet have a matching user
        self.load_users_as_necessary()

    def grab_user_images_slice(self) -> tuple[np.ndarray, Pxy]:
        x = 116 # user images are typically at x=116
        y = 0
        w = 50 # user images are very small
        h = self.discord_frame_grabber.monitor_area.height
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
        newly_located_users: list[User] = []
        annotated_slice = slice.copy()

        for user in self.users:
            voice_icon = user.cropped_voice_icon

            # Start by matching off the corner pixels (and center pixel).
            # We do this for speed, since np.where and np.logical_and are much
            # faster than scanning through the entire slice for the user image.
            w, h = voice_icon.shape[1], voice_icon.shape[0]
            sample_pixels = Rect.from_xywh(0, 0, w, h).get_corners_xy(True)
            sample_pixels.append(Pxy(int(w/2), int(h/2)))
            matches: list[bool] = []
            for i, pixel in enumerate(sample_pixels):
                shifted_slice = slice[pixel.y:slice.shape[0]-(h-pixel.y-1), pixel.x:slice.shape[1]-(w-pixel.x-1)]
                if i == 0:
                    matches = shifted_slice == voice_icon[pixel.y, pixel.x]
                else:
                    matches = np.logical_and(matches, shifted_slice == voice_icon[pixel.y, pixel.x])
            matching_coords = np.where(matches)

            # Search for exact matches to our approximate matches
            x_searches, y_searches = matching_coords[1].tolist(), matching_coords[0].tolist()
            match: Rect = None
            for x, y in zip(x_searches, y_searches):
                if x+w <= slice.shape[1] and y+h <= slice.shape[0]:
                    if np.all(slice[y:y+h, x:x+w] == voice_icon):
                        match = Rect.from_xywh(x, y, w, h)
                        break
            if match is None:
                continue

            # Add the match to our return value
            window_rel_match = match + window_offset
            user.voice_icon_region = window_rel_match
            newly_located_users.append(user)

            # Debugging: draw the rectangle on large_image
            magenta = (255,0,255)
            annotated_slice = cv2.rectangle(annotated_slice, match.top_left.astuple(), match.bottom_right.astuple(), magenta, thickness=2)
        
        # Sort users by their y-location
        newly_located_users = sorted(newly_located_users, key=lambda u: u.voice_icon_region.y)
        
        return newly_located_users, annotated_slice