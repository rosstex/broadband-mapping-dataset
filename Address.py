class Address:
	def __init__(self, firstline, zipcode, city, state,secondline=None, apt_type='', apt_number=''):
		self.line1 = firstline
		self.line2 = secondline
		self.city = city
		self.state = state
		self.zipcode = zipcode
		self.apt_type = apt_type
		self.apt_number = apt_number

	def fullAddressNoZip(self):
		line = self.line1
		if self.city is not None and self.state is not None:
			line = line + ", " + self.city + ", " + self.state
		return line

	def fullAddress(self):
		line = self.line1
		if self.city is not None and self.state is not None:
			line = line + ", " + self.city + ", " + self.state + ", " + self.zipcode
		return line

	def fullAddressNoCommas(self):
		line = self.line1
		if self.city is not None and self.state is not None:
			line = line + " " + self.city + " " + self.state + " " + self.zipcode
		return line

	def fullAddressWithApt(self):
		if self.apt_type == None:
			self.apt_type = ''
		if self.apt_number == None:
			self.apt_number = ''
		line = self.line1
		if self.apt_type != '' and self.apt_number != '':
			line += ", " + self.apt_type + " " + self.apt_number
		elif self.apt_number != '':
			line += ', ' + self.apt_number
		line += ", " + self.city + ", " + self.state + ", " + self.zipcode
		return line

	def fullAddressForCenturyLink(self):
		return