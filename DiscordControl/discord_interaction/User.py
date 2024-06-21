import os
import sys
from dataclasses import dataclass

sys.path.append(os.path.normpath(os.path.join(__file__, "..")))
from geometry import Rect


@dataclass
class User():
    voice_icon_path_name_ext: str
    """ path/name.ext of the voice icon for this user """
    voice_icon_region: Rect
    """ location of the voice icon for this user,
    in screen coordinates, relative to the discord window """

    @property
    def voice_icon_name_ext(self) -> str:
        os.path.basename(self.voice_icon_path_name_ext)

    @property
    def voice_icon_path(self) -> str:
        os.path.dirname(self.voice_icon_path_name_ext)