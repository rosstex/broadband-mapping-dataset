class CoverageResult:
	def __init__(self, is_covered, max_upspeed='', max_downspeed=''):
		self.is_covered = is_covered
		self.down_speed = max_downspeed
		self.up_speed = max_upspeed
