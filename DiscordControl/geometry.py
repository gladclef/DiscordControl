import numpy as np


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