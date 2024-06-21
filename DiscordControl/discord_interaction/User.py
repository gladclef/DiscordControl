import os
import sys

sys.path.append(os.path.normpath(os.path.join(__file__, "..")))
from geometry import Rect


class User():
    def __init__(self, voice_icon_path_name_ext: str, voice_icon_region: Rect):
        self.voice_icon_path_name_ext = voice_icon_path_name_ext
        """ path/name.ext of the voice icon for this user """
        self.voice_icon_region = voice_icon_region
        """ location of the voice icon for this user,
        in screen coordinates, relative to the discord window """

        self.voice_icon_name_ext = os.path.basename(self.voice_icon_path_name_ext)
        self.voice_icon_path = os.path.dirname(self.voice_icon_path_name_ext)