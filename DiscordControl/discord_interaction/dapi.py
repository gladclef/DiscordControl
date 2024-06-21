import os
import sys
import time

import cv2 as cv
import numpy as np
from PIL import Image
from pynput.keyboard import Controller as Keyboard
from pynput.keyboard import Key
from pynput.mouse import Button
from pynput.mouse import Controller as Mouse

sys.path.append(os.path.normpath(os.path.join(__file__, "..", "..")))
from discord_interaction.DiscordWindowFinder import DiscordWindowFinder
from discord_interaction.LocatorUserImages import LocatorUserImages
from discord_interaction.User import User
from Fresh import Fresh
from geometry import Pxy, Rect

app_images_dir = "C:/Users/gladc/OneDrive/Documents/3d prints/deej/software/pics"
user_images_dir = "C:/Users/gladc/OneDrive/Documents/3d prints/deej/software/pics/user_pics"

keyboard = Keyboard()
mouse = Mouse()


class _DiscordAPI():
    def __init__(self, app_images_dir: str, user_images_dir: str):
        self.app_images_dir = app_images_dir
        self.user_images_dir = user_images_dir
        self.discord_window = DiscordWindowFinder()
        self.user_locator = LocatorUserImages(self.discord_window, user_images_dir)

        self.users: Fresh[list[User]] = Fresh(lambda: self.user_locator.locate_users_annotations()[0])
        self.mic_center_for_grabbing: Fresh[Pxy] = Fresh(self._get_mic_center_for_grabbing)
        self.mic_image: np.ndarray = None
        self.mic_mask: np.ndarray = None

    def update(self):
        """ Allows all Fresh values to update, as necesssary.
        Useful for maintaining a consistent state during evaluation.
        Should be called at the start of an evaluation. """
        # unlock all Fresh values
        self.users.unlock()

        # if the window isn't visible, then we activate it to bring it to the foreground
        if self.num_users == 0:
            self.discord_window.activate_window()

        # mark all Fresh values as needing to update
        self.users.needs_refresh = True

        # lock all Fresh values
        self.users.lock()
    
    @property
    def num_users(self):
        return len(self.users.get())
    
    def get_user_by_index(self, idx: int) -> User:
        if self.num_users == 0:
            return None
        idx %= self.num_users
        return self.users.get()[idx]
    
    def get_user_by_name(self, partial_name: str) -> User:
        for user in self.users.get():
            if partial_name in user.voice_icon_name_ext:
                return user
        return None
    
    def _get_mic_center_for_grabbing(self):
        radius = Pxy(30, 30)

        # grab a portion of the screen roughly corresponding to where the mic is
        voice_status_corner_approx = self.discord_window.virtual_coord(Pxy(80, -152), 'bl')
        mic_center_approx = voice_status_corner_approx + Pxy(152, 116)
        mic_region_approx = Rect(mic_center_approx - radius, mic_center_approx + radius)
        mic_image = self.discord_window.grab(mic_region_approx - self.discord_window.window_corner())

        # convert to black and white
        thresholded = np.zeros(mic_image.shape[:2], dtype=mic_image.dtype)
        thresholded[np.where(mic_image[:, :, 0] > 150)] = 255

        # find the best matching location
        if self.mic_image is None:
            mic_path = os.path.normpath(os.path.join(self.app_images_dir, "mic_thresholded.png"))
            mic_mask_path = os.path.normpath(os.path.join(self.app_images_dir, "mic_mask.png"))
            self.mic_image = np.array(Image.open(mic_path))[:, :, 0].squeeze()
            self.mic_mask = np.array(Image.open(mic_mask_path))[:, :, 0].squeeze()
        match_matrix = cv.matchTemplate(thresholded, self.mic_image, cv.TM_SQDIFF, mask=self.mic_mask)
        _, _, match_loc_xy, _ = cv.minMaxLoc(match_matrix)
        match_loc = Pxy(match_loc_xy[0], match_loc_xy[1])

        # use this value as an offset from the expected center
        match_ul = mic_center_approx - radius + match_loc
        return match_ul + (Pxy(self.mic_image.shape[1], self.mic_image.shape[0]) / 2)
    
    def is_muted(self) -> bool:
        # activate the discord window
        self.discord_window.activate_window()

        # grab the mic image
        voice_status_corner = self.discord_window.virtual_coord(Pxy(80, -152), 'bl')
        mic_center = self.mic_center_for_grabbing.get()
        mic_region = Rect(mic_center - Pxy(13, 13), mic_center + Pxy(13, 13))
        mic_image = self.discord_window.grab(mic_region - self.discord_window.window_corner())

        # return true if red
        thresholded = np.zeros_like(mic_image)
        thresholded[np.where(mic_image > 150)] = 1
        r, g, b = np.sum(thresholded[:,:,0]), np.sum(thresholded[:,:,1]), np.sum(thresholded[:,:,2])
        if r > (g + b):
            return True
        return False

    
dapi = _DiscordAPI(app_images_dir, user_images_dir)


def set_user_volume(user_idx_or_name: int | str, volume_0_100: int):
    dapi.update()

    # normalize the input
    volume_0_100 = np.clip(volume_0_100, 0, 100)

    # get the user
    if isinstance(user_idx_or_name, str):
        user = dapi.get_user_by_name(user_idx_or_name)
    else:
        user = dapi.get_user_by_index(user_idx_or_name)
    if user is None:
        raise ValueError(f"User with name or index {user_idx_or_name} can't be found!")
    
    # activate the discord window
    dapi.discord_window.activate_window()

    # close any existing ui elements
    keyboard.tap(Key.esc)
    keyboard.tap(Key.esc)

    # open the user's context menu
    user_loc = dapi.discord_window.virtual_coord(user.voice_icon_region.top_left)
    mouse.position = (user_loc + Pxy(5, 5)).astuple()
    mouse.click(Button.right)

    # get the location of the volume slider
    # X is between 16 and 171
    x_range = 171 - 16
    x_rel_pos = 16 + np.clip(np.round([x_range / 100 * volume_0_100]), 0, x_range)
    # Y is always at relative position 257
    y_rel_pos = 257

    # set the user's volume
    volume_pos = Pxy(mouse.position[0] + x_rel_pos, mouse.position[1] + y_rel_pos)
    mouse.position = volume_pos.astuple()
    mouse.click(Button.left)
    

def mute():
    dapi.update()
    
    # activate the discord window
    dapi.discord_window.activate_window()

    # determine if we're currently muted
    if not dapi.is_muted():
        mouse.position = dapi.mic_center_for_grabbing.get().astuple()
        mouse.click(Button.left)


def unmute():
    dapi.update()
    
    # activate the discord window
    dapi.discord_window.activate_window()

    # determine if we're currently muted
    if dapi.is_muted():
        mouse.position = dapi.mic_center_for_grabbing.get().astuple()
        mouse.click(Button.left)
    

if __name__ == "__main__":
    unmute()