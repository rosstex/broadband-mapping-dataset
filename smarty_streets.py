def add_smarty_info():

for state in ['NY']:
	print(f'State: {state}')

	mydb = mysql.connector.connect(
		host="localhost",
		user="root",
		passwd="",
		database="{}_addresses".format(state)
	)
	mycursor = mydb.cursor(buffered=True)

	# Only for first run - add the new column
	if False:
		# Alter state address table to include dpb/rdi 
		mycursor.execute(
			"ALTER TABLE   addresses_{} ADD COLUMN ( \
				addr_dpv						VARCHAR(255), \
				addr_rdi			VARCHAR(255) \
			)".format(state)
		)
		print('Altered address table for {}'.format(state))



	if state == 'VA':
		mycursor.execute(f"SELECT addr_num, addr_city, addr_state, addr_zip, addr_id, addr_full, addr_street FROM addresses_{state} WHERE addr_dpv is not null ")
	else:
		mycursor.execute(f"SELECT addr_line1, addr_city, addr_state, addr_zip, addr_id, addr_full FROM addresses_{state} WHERE addr_dpv is not null and addr_id > 4672160")
	result = mycursor.fetchall()
	data = list()
	input_addresses = list()
	addresses = dict()

	print('Count: {}'.format(len(result)))

	for i,row in enumerate(result):

		#print(row)
		if state == 'VA':
			line1 = row[0] + ' ' + row[6]
		else:
			line1 = row[0]
		# Bug that makes the request fail
		if '\'' in line1 or 'Ë' in line1 or 'Ö' in line1 or '’' in line1:
			line1 = line1.replace('\'','')
			line1 = line1.replace('Ë','')
			line1 = line1.replace('Ö','')
			line1 = line1.replace('’','')

		city = row[1]
		# Bug that makes the request fail
		if '\'' in city:
			city = city.replace('\'','')

		#state = row[2]
		zipcode = row[3]
		addr_id = str(row[4])
		addr_full = row[5]
		addresses[addr_id] = addr_full

		data.append({
			"street":line1.upper(),
			"city":city.upper(),
			"state":state.upper(),
			"zipcode":zipcode,
			"candidates":1,
			"input_id": str(addr_id),
		})
		input_addresses.append(addr_id)

		# Make the request
		if len(data) == 99 or i == len(result)-1:
			returned_addresses = defaultdict(lambda: list())

			#pp.pprint(data)

			url = f"https://us-street.api.smartystreets.com/street-address?auth-id=72ee1c95-9ed9-61bd-bf61-d104c39469d6&" + \
				f"auth-token=t6gv3XdxInKrDhg7mQVQ"
			headers = {"Content-Type": "application/json", "charset":"utf-8"}
			data = str(data).replace('\'','"')

			for _ in range(3):
				try:
					responses = None
					r = requests.post(url=url,headers=headers, data=data)
					responses = r.json()
					break
				except KeyboardInterrupt:
					raise
				except:
					pass
			if responses == None:
				raise Exception()

			#pp.pprint(responses)

			# Store all responses
			for address_json in responses:
				returned_addresses[address_json.get('input_id')].append(address_json)
				#pp.pprint(returned_addresses)
		
			# For each inputted address id, see what the result is (or if it doesn't exist at all)
			for addr_id in input_addresses:
				response = returned_addresses[addr_id]

				if response == []:
					dpv = 'U'
					rdi = 'N'
				elif len(response) > 1:
					print('GREATER THAN 1')
					print(addr_id)
					print(response)
					raise Exception()
				elif len(response) == 1:
					dpv_match_code = response[0].get('analysis').get('dpv_match_code')

					if dpv_match_code in ['Y','N','S','D']:
						dpv = dpv_match_code
					else:
						print('ISSUE')
						print(dpv_match_code)
						raise Exception()

					# Get address/commerical info
					if dpv_match_code in ['Y','S','D']:
						if response[0].get('metadata').get('rdi') == 'Residential':
							rdi = 'R'
						elif response[0].get('metadata').get('rdi') == 'Commercial':
							rdi = 'C'
						elif response[0].get('metadata').get('rdi') == None:
							rdi = 'E'
						else:
							pp.pprint(response)
							print(response[0].get('metadata').get('rdi'))
							raise Exception()
					else:
						rdi = 'N'

					#pp.pprint(response)
				else:
					print(response)
					raise Exception()

				# Update dpv and rdi for the address
				mycursor.execute("UPDATE addresses_{} \
					SET addr_dpv = '{}', \
						addr_rdi = '{}' \
					WHERE addr_id = {} \
					".format(
							state,
							dpv, 
							rdi,
							addr_id)
					)

			# Print most recent result
			print(addr_id)
			print(addresses[addr_id])
			print(dpv)
			print(rdi)

			# Reset values
			input_addresses = list()
			data = list()
			addresses = dict()

			mydb.commit()

	print('Finished all addresses...')
	mydb.commit()