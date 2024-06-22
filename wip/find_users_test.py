import os
import sys

from PIL import Image

sys.path.append(os.path.normpath(os.path.join(__file__, "..", "..")))
from discord_interaction.DiscordWindowFinder import DiscordWindowFinder
from discord_interaction.LocatorUserImages import LocatorUserImages
from geometry import Pxy, Rect

if __name__ == "__main__":
	user_images_dir = "C:/Users/gladc/OneDrive/Documents/3d prints/deej/software/pics/user_pics"

	grabber = DiscordWindowFinder()
	user_locator = LocatorUserImages(grabber, user_images_dir)
	user_images_regions, annotated = user_locator.locate_names_regions_annotations()
	for name in user_images_regions:
		print(f"{name}: {user_images_regions[name]}")
	img = Image.fromarray(annotated)
	img.show()
