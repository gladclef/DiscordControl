import os
import sys
from enum import Enum

import numpy as np
from PIL import Image

sys.path.append(os.path.normpath(os.path.join(__file__, "..")))
from geometry import Rect


class UpdateStatus(Enum):
    unchanged = 0
    reloaded = 1
    unloaded = 2


class User():
    def __init__(self, voice_icon_path_name_ext: str, voice_icon_region: Rect = None):
        self.voice_icon_path_name_ext = voice_icon_path_name_ext
        """ path/name.ext of the voice icon for this user """
        self.voice_icon_region = voice_icon_region
        """ location of the voice icon for this user,
        in screen coordinates, relative to the discord window """

        self.voice_icon = Image.open(self.voice_icon_path_name_ext)
        self._cropped_voice_icon: np.ndarray = None
        self.voice_icon_name_ext = os.path.basename(self.voice_icon_path_name_ext)
        self.voice_icon_path = os.path.dirname(self.voice_icon_path_name_ext)
        self.voice_icon_mtime = os.path.getmtime(self.voice_icon_path_name_ext)
    
    @property
    def cropped_voice_icon(self) -> np.ndarray:
        if self._cropped_voice_icon is None:
            self._cropped_voice_icon = np.array(self.voice_icon)[6:18, 6:18, :3]
        return self._cropped_voice_icon

    def update_as_necessary(self) -> UpdateStatus:
        """ Reloads or unloads the image for this user from the source image file, as necessary. """
        if not os.path.isfile(self.voice_icon_path_name_ext):
            self.voice_icon = None
            return UpdateStatus.unloaded

        new_mod_time = os.path.getmtime(self.voice_icon_path_name_ext)
        if new_mod_time > self.voice_icon_mtime:
            self.voice_icon = Image.open(self.voice_icon_path_name_ext)
            self._cropped_voice_icon = None
            self.voice_icon_mtime = new_mod_time
            return UpdateStatus.reloaded
        
        return UpdateStatus.unchanged
    

        